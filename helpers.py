import sqlite3
import pickle
import spacy
# noinspection PyUnresolvedReferences
from tensorflow.keras.models import load_model
# noinspection PyUnresolvedReferences
from tensorflow.keras.preprocessing.sequence import pad_sequences

class RecipeProcessor:
    def __init__(self):
        self.model = None
        self.nlp = None
        self.vocab = None
        self.max_len = 2000
        self.init_resources()
        self.init_db()

    #Инициализация ресурсов для нейронной сети
    def init_resources(self):
        try:
            self.nlp = spacy.load("ru_core_news_sm")
            with open('minimal_data.pkl', 'rb') as f:
                data = pickle.load(f)
                self.vocab = data['vocab']
            self.model = load_model('recognize_model.keras')
        except Exception as e:
            raise RuntimeError(f"Failed to initialize resources: {str(e)}")

    #Метод фильтрации токенов
    def _filter(self, token):
        if len(token.text) < 2:
            return False
        if token.is_stop:
            return False
        if not token.text[0].isalpha():
            return False
        if token.is_digit or token.like_num:
            return False
        return True

    #Подготавливает данные для передачи в нейронную сеть
    def prepare_sequences(self, texts):
        if not self.vocab:
            raise ValueError("Vocabulary not loaded")
        X = [[self.vocab.get(w.text, self.vocab["<UNK>"]) for w in s] for s in texts]
        return pad_sequences(
            maxlen=self.max_len,
            sequences=X,
            padding="post",
            value=self.vocab["<PAD>"]
        )

    #Основной метод выделения ингредиентов при помощи нейронной сети
    def extract_ingredients(self, text, threshold=0.4):
        if not self.model or not self.nlp:
            raise RuntimeError("Processor not properly initialized")
        doc = self.nlp(text)
        test_tokenized = [doc]
        test_seq = self.prepare_sequences(test_tokenized)
        predictions = self.model.predict(test_seq)
        ingredients = []
        current_ingredient = []
        for token, prob in zip(doc, predictions[0]):
            prob_value = float(prob)
            is_ingredient = prob_value > threshold
            filter_passed = self._filter(token)
            if is_ingredient and filter_passed:
                current_ingredient.append(token)
            else:
                if current_ingredient:
                    start = current_ingredient[0].idx
                    end = current_ingredient[-1].idx + len(current_ingredient[-1].text)
                    ingredient = text[start:end].strip()
                    if ingredient not in ingredients:
                        ingredients.append(ingredient)
                    current_ingredient = []
        if current_ingredient:
            start = current_ingredient[0].idx
            end = current_ingredient[-1].idx + len(current_ingredient[-1].text)
            ingredient = text[start:end].strip()
            if ingredient not in ingredients:
                ingredients.append(ingredient)
        return sorted(ingredients)

    #Инициализирует подключение к базе данных
    def init_db(self):
        self.conn = sqlite3.connect('recipes.db')
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._create_triggers()

    #Создаёт необходимые таблицы в базе данных
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                ingredients TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipe_categories (
                recipe_id INTEGER,
                category_id INTEGER,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id),
                FOREIGN KEY (category_id) REFERENCES categories(id),
                PRIMARY KEY (recipe_id, category_id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingredient_quantities (
                recipe_id INTEGER,
                ingredient TEXT,
                quantity TEXT,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id),
                PRIMARY KEY (recipe_id, ingredient)
            )
        ''')
        self.conn.commit()

    #Создаёт триггеры в базе данных
    def _create_triggers(self):
        self.cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS add_default_category
            AFTER INSERT ON recipes
            BEGIN
                INSERT OR IGNORE INTO categories (name) VALUES ('Все');
                INSERT OR IGNORE INTO recipe_categories (recipe_id, category_id)
                VALUES (NEW.id, (SELECT id FROM categories WHERE name = 'Все'));

                INSERT OR IGNORE INTO categories (name) VALUES ('Избранное');
            END
        ''')
        self.cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS delete_empty_categories
            AFTER DELETE ON recipe_categories
            BEGIN
                DELETE FROM categories
                WHERE id IN (
                    SELECT c.id FROM categories c
                    LEFT JOIN recipe_categories rc ON c.id = rc.category_id
                    WHERE rc.category_id IS NULL AND c.name NOT IN ('Все', 'Избранное')
                );
            END
        ''')
        self.conn.commit()

    # Методы, обеспечивающие CRUD-операции для рецептов и ингредиентов
    #Возвращает все рецепты отсортированные по имени
    def get_recipes(self):
        self.cursor.execute("SELECT id, name FROM recipes ORDER BY name")
        return self.cursor.fetchall()
    #Возвращает всю информацию о рецепте по его ID
    def get_recipe(self, recipe_id):
        self.cursor.execute("SELECT name, text, ingredients FROM recipes WHERE id = ?", (recipe_id,))
        result = self.cursor.fetchone()
        if result:
            return {
                'name': result[0],
                'text': result[1],
                'ingredients': result[2].split('\n') if result[2] else []
            }
        return None
    #Создаёт новый рецепт в базе данных
    def create_recipe(self, name, text, ingredients=None):
        ingredients_text = '\n'.join(ingredients) if ingredients else ''
        self.cursor.execute(
            "INSERT INTO recipes (name, text, ingredients) VALUES (?, ?, ?)",
            (name, text, ingredients_text)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    #Обновляет рецепт
    def update_recipe(self, recipe_id, name, text, ingredients=None):
        ingredients_text = '\n'.join(ingredients) if ingredients else ''
        self.cursor.execute(
            "UPDATE recipes SET name = ?, text = ?, ingredients = ? WHERE id = ?",
            (name, text, ingredients_text, recipe_id)
        )
        self.conn.commit()
    #Удаляет рецепт
    def delete_recipe(self, recipe_id):
        self.cursor.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (recipe_id,))
        self.cursor.execute("DELETE FROM ingredient_quantities WHERE recipe_id = ?", (recipe_id,))
        self.cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        self.conn.commit()
    #Выполняет поиск рецепта по названию и категории
    def search_recipes(self, search_term):
        self.cursor.execute('''
            SELECT DISTINCT r.id, r.name
            FROM recipes r
            LEFT JOIN recipe_categories rc ON r.id = rc.recipe_id
            LEFT JOIN categories c ON rc.category_id = c.id
            WHERE r.name LIKE ? OR c.name LIKE ?
            ORDER BY r.name
        ''', (f"%{search_term}%", f"%{search_term}%"))
        return self.cursor.fetchall()
    #Получает список ингредиентов конкретного рецепта
    def get_recipe_ingredients(self, recipe_id):
        self.cursor.execute("SELECT ingredients FROM recipes WHERE id = ?", (recipe_id,))
        result = self.cursor.fetchone()
        return result[0].split('\n') if result and result[0] else []
    #Получает информацию о количестве ингредиентов в рецепте
    def get_ingredient_quantities(self, recipe_id):
        self.cursor.execute("SELECT ingredient, quantity FROM ingredient_quantities WHERE recipe_id = ?", (recipe_id,))
        return dict(self.cursor.fetchall())
    #Обновляет значения количества ингредиентов в рецепте
    def update_ingredient_quantities(self, recipe_id, quantities):
        self.cursor.execute("DELETE FROM ingredient_quantities WHERE recipe_id = ?", (recipe_id,))
        for ingredient, quantity in quantities.items():
            self.cursor.execute(
                "INSERT INTO ingredient_quantities (recipe_id, ingredient, quantity) VALUES (?, ?, ?)",
                (recipe_id, ingredient, quantity)
            )
        self.conn.commit()
    #Обновляет список ингредиентов рецепта
    def update_recipe_ingredients(self, recipe_id, ingredients):
        ingredients_text = '\n'.join(ingredients) if ingredients else ''
        self.cursor.execute(
            "UPDATE recipes SET ingredients = ? WHERE id = ?",
            (ingredients_text, recipe_id)
        )
        self.conn.commit()


    # Методы, обеспечивающие CRUD-операции для категорий
    #Возвращает список всех доступных категорий рецептов
    def get_categories(self):
        self.cursor.execute("SELECT id, name FROM categories")
        return self.cursor.fetchall()
    #Добавляет новую категорию
    def add_category(self, name):
        self.cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        self.conn.commit()
        return self.cursor.lastrowid
    #Удаляет категорию
    def delete_category(self, category_id):
        self.cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
        category_name = self.cursor.fetchone()[0]
        if category_name == 'Все':
            return False
        self.cursor.execute("DELETE FROM recipe_categories WHERE category_id = ?", (category_id,))
        self.cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()
        return True
    #Создаёт связь между рецептом и категорией
    def add_recipe_to_category(self, recipe_id, category_id):
        self.cursor.execute(
            "INSERT OR IGNORE INTO recipe_categories (recipe_id, category_id) VALUES (?, ?)",
            (recipe_id, category_id)
        )
        self.conn.commit()
    #Возвращает название категории по ее ID
    def get_category_by_id(self, category_id):
        self.cursor.execute("SELECT id, name FROM categories WHERE id = ?", (category_id,))
        return self.cursor.fetchone()
    #Удаляет связь между рецептом и категорией
    def remove_recipe_from_category(self, recipe_id, category_id):
        category = self.get_category_by_id(category_id)
        if not category:
            return False
        category_name = category[1]

        if category_name == 'Все':
            return False
        try:
            self.cursor.execute(
                "DELETE FROM recipe_categories WHERE recipe_id = ? AND category_id = ?",
                (recipe_id, category_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error removing recipe from category: {e}")
            return False
    #Возвращает список категорий рецепта
    def get_recipe_categories(self, recipe_id):
        self.cursor.execute('''
            SELECT c.id, c.name
            FROM categories c
            JOIN recipe_categories rc ON c.id = rc.category_id
            WHERE rc.recipe_id = ?
        ''', (recipe_id,))
        return self.cursor.fetchall()

    def close(self):
        if hasattr(self, 'conn'):
            self.conn.close()
        if hasattr(self, 'nlp'):
            self.nlp = None
