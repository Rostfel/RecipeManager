import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTextEdit, QLineEdit, QPushButton, QLabel,
    QMessageBox, QInputDialog, QListWidgetItem, QFileDialog, QSizePolicy,
    QCheckBox, QFrame, QMenu, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
from helpers import RecipeProcessor

class RecipeApp(QMainWindow):
    #Инициализирует главное окно, класс RecipeProcessor, стили приложения, создаёт папки для изображений
    def __init__(self):
        super().__init__()
        self.processor = RecipeProcessor()
        self.recipe_images_dir = "content/recipe_images"
        os.makedirs(self.recipe_images_dir, exist_ok=True)
        self.setup_ui()
        self.connect_signals()
        self.load_recipes()
        self.current_ingredients = []
        self.selected_recipe_id = None
        self.load_stylesheet("content/default_theme.qss")
    #Применяет стили
    def load_stylesheet(self, filename):
        try:
            with open(filename, "r") as file:
                stylesheet = file.read()
            QApplication.instance().setStyleSheet(stylesheet)
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")
    #Создание интерфейса
    def setup_ui(self):
        self.setWindowTitle("Менеджер Рецептов")
        self.resize(1200, 800)
        self.setMinimumHeight(350)
        self.showMaximized()
        self.raise_()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.left_panel = QVBoxLayout()
        self.left_panel.setObjectName("left_panel")
        self.left_panel.setContentsMargins(0, 0, 0, 0)
        self.left_panel.setSpacing(10)

        self.search_bar = QLineEdit(placeholderText="Поиск рецептов...")
        self.search_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.recipe_list = RecipeListWidget()
        self.recipe_list.setObjectName("recipe_list")
        self.recipe_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.left_panel.addWidget(QLabel("Рецепты"))
        self.left_panel.addWidget(self.search_bar)
        self.left_panel.addWidget(self.recipe_list)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(5)

        self.add_recipe_button = QPushButton("Добавить Новый Рецепт")
        self.add_recipe_button.setObjectName("add_recipe_button")
        self.delete_button = QPushButton("Удалить Выбранный Рецепт")
        self.delete_button.setObjectName("delete_button")
        self.order_button = QPushButton("Заказать Ингредиенты")
        self.order_button.setObjectName("order_button")
        button_layout.addWidget(self.add_recipe_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.order_button)
        self.left_panel.addLayout(button_layout)

        self.middle_panel = QVBoxLayout()
        self.middle_panel.setObjectName("middle_panel")
        self.middle_panel.setContentsMargins(0, 0, 0, 0)
        self.middle_panel.setSpacing(10)

        self.recipe_name = QLineEdit(placeholderText="Название рецепта...")
        self.recipe_name.setObjectName("recipe_name")

        self.recipe_text = QEnhancedTextEdit(placeholderText="Вставьте рецепт сюда...")
        self.recipe_text.setObjectName("recipe_text")
        self.recipe_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        button_row = QHBoxLayout()
        button_row.setSpacing(5)
        self.extract_button = QPushButton("Найти Ингредиенты")
        self.extract_button.setObjectName("extract_button")
        self.save_button = QPushButton("Сохранить Рецепт")
        self.save_button.setObjectName("save_button")
        button_row.addWidget(self.extract_button)
        button_row.addWidget(self.save_button)

        self.middle_panel.addWidget(self.recipe_name)
        self.middle_panel.addWidget(self.recipe_text)
        self.middle_panel.addLayout(button_row)

        self.right_panel = QVBoxLayout()
        self.right_panel.setObjectName("right_panel")
        self.right_panel.setContentsMargins(0, 0, 0, 0)
        self.right_panel.setSpacing(10)

        self.ingredients_table = QTableWidget()
        self.ingredients_table.setObjectName("ingredients_table")
        self.ingredients_table.setColumnCount(2)
        self.ingredients_table.setHorizontalHeaderLabels(["Ингредиенты", "Количество"])
        self.ingredients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ingredients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ingredients_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.ingredients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ingredients_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ingredients_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ingredients_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ingredients_table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ingredients_table.setShowGrid(False)

        self.right_panel.addWidget(self.ingredients_table)

        ingredients_buttons = QVBoxLayout()
        ingredients_buttons.setSpacing(5)
        self.add_ingredient_btn = QPushButton("Добавить")
        self.add_ingredient_btn.setObjectName("add_ingredient_btn")
        self.edit_ingredient_btn = QPushButton("Редактировать")
        self.edit_ingredient_btn.setObjectName("edit_ingredient_btn")
        self.remove_ingredient_btn = QPushButton("Удалить")
        self.remove_ingredient_btn.setObjectName("remove_ingredient_btn")

        ingredients_buttons.addWidget(self.add_ingredient_btn)
        ingredients_buttons.addWidget(self.edit_ingredient_btn)
        ingredients_buttons.addWidget(self.remove_ingredient_btn)

        self.right_panel.addLayout(ingredients_buttons)

        left_widget = QWidget()
        left_widget.setLayout(self.left_panel)
        left_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        left_widget.setMinimumWidth(int(self.width() * 0.35))

        middle_widget = QWidget()
        middle_widget.setLayout(self.middle_panel)
        middle_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_widget = QWidget()
        right_widget.setLayout(self.right_panel)
        right_widget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)

        main_layout.addWidget(left_widget, 2)
        main_layout.addWidget(middle_widget, 3)
        main_layout.addWidget(right_widget, 2)

        self.recipe_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recipe_list.customContextMenuRequested.connect(self.show_recipe_context_menu)

        self.statusBar().showMessage("Готово")
    #Соединяет сигналы виджетов с их обработчиками
    def connect_signals(self):
        self.recipe_list.itemClicked.connect(self.load_recipe)
        self.search_bar.textChanged.connect(self.search_recipes)
        self.extract_button.clicked.connect(self.extract_ingredients)
        self.save_button.clicked.connect(self.save_recipe)
        self.order_button.clicked.connect(self.order_ingredients)
        self.delete_button.clicked.connect(self.delete_recipe)
        self.add_recipe_button.clicked.connect(self.add_new_recipe)
        self.add_ingredient_btn.clicked.connect(self.add_ingredient)
        self.edit_ingredient_btn.clicked.connect(self.edit_ingredient)
        self.remove_ingredient_btn.clicked.connect(self.remove_ingredients)
    #Отображает контекстное меню
    def show_recipe_context_menu(self, position):
        item = self.recipe_list.itemAt(position)
        if not item:
            return
        recipe_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        categories = self.processor.get_categories()
        recipe_categories = self.processor.get_recipe_categories(recipe_id)
        add_to_category_menu = menu.addMenu("Добавить в категорию")
        favorite_category = next((cat for cat in categories if cat[1] == "Избранное"), None)
        in_favorites = any(cat[1] == "Избранное" for cat in recipe_categories)
        if not in_favorites and favorite_category:
            favorites_action = add_to_category_menu.addAction("Избранное")
            favorites_action.triggered.connect(
                lambda: self.add_recipe_to_category(recipe_id, favorite_category[0])
            )
        for category_id, category_name in categories:
            if category_name not in ["Все", "Избранное"] and not any(
                    cat[1] == category_name for cat in recipe_categories):
                action = add_to_category_menu.addAction(category_name)
                action.triggered.connect(lambda _, cid=category_id: self.add_recipe_to_category(recipe_id, cid))
        add_new_category_action = add_to_category_menu.addAction("Создать новую категорию...")
        add_new_category_action.triggered.connect(lambda: self.create_new_category(recipe_id))
        remove_from_category_menu = menu.addMenu("Удалить из категории")
        has_removable = False
        for category_id, category_name in recipe_categories:
            if category_name == "Избранное" or category_name not in ["Все"]:
                action = remove_from_category_menu.addAction(category_name)
                action.triggered.connect(lambda _, cid=category_id: self.remove_recipe_from_category(recipe_id, cid))
                has_removable = True
        if not has_removable:
            remove_from_category_menu.setEnabled(False)
        menu.exec(self.recipe_list.viewport().mapToGlobal(position))
    #Создаёт связь между категорией и рецептом
    def add_recipe_to_category(self, recipe_id, category_id):
        self.processor.add_recipe_to_category(recipe_id, category_id)
        self.statusBar().showMessage(f"Рецепт добавлен в категорию", 3000)
        self.load_recipes()
    #Удаляет категорию у рецепта
    def remove_recipe_from_category(self, recipe_id, category_id):
        category = self.processor.get_category_by_id(category_id)
        if not category:
            print(f"Category with ID {category_id} not found")
            return False
        category_name = category[1]
        if category_name == "Все":
            return False
        if self.processor.remove_recipe_from_category(recipe_id, category_id):
            self.statusBar().showMessage(f"Рецепт удален из категории {category_name}", 3000)
            self.load_recipes()
            return True
        return False
    #Создаёт новую категорию и добавляет в нее рецепт
    def create_new_category(self, recipe_id):
        category_name, ok = QInputDialog.getText(self, "Создать новую категорию", "Введите название категории:")
        if ok and category_name.strip():
            category_id = self.processor.add_category(category_name.strip())
            self.processor.add_recipe_to_category(recipe_id, category_id)
            self.statusBar().showMessage(f"Создана новая категория: {category_name}", 3000)
            self.load_recipes()
    #Загружает рецепты из базы данных, создаёт для каждого рецепта виджет, обрабатывает изображения
    def load_recipes(self):
        self.recipe_list.clear()
        recipes = self.processor.get_recipes()
        for recipe_id, name in recipes:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, recipe_id)
            img_path = self.get_recipe_image_path(recipe_id)
            if not os.path.exists(img_path):
                img_path = "content/placeholder_image.png"
            widget = RecipeListItemWidget(name, recipe_id, img_path)
            widget.image_clicked.connect(self.change_recipe_image)
            categories = self.processor.get_recipe_categories(recipe_id)
            for category_id, category_name in categories:
                if category_name != "Все":
                    widget.add_category_tag(category_name, category_id, lambda cid=category_id: self.remove_recipe_from_category(recipe_id, cid))
            item.setSizeHint(QSize(200, 100))
            self.recipe_list.addItem(item)
            self.recipe_list.setItemWidget(item, widget)
            self.recipe_list.resizeEvent(None)
    #Возвращает путь до изображения рецепта
    def get_recipe_image_path(self, recipe_id):
        return os.path.join(self.recipe_images_dir, f"{recipe_id}.png")
    #Открывает диалог выбора изображения, сохраняет и обновляет превью
    def change_recipe_image(self, recipe_id):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите Изображение Рецепта",
            "",
            "Изображения (*.png *.jpeg *.jpg *.bmp)"
        )
        if file_path:
            target_path = self.get_recipe_image_path(recipe_id)
            if os.path.exists(target_path):
                os.remove(target_path)
            img = QImage(file_path)
            img.save(target_path, "png")
            self.load_recipes()
            if self.selected_recipe_id == recipe_id:
                self.load_recipe_by_id(recipe_id)
    #Загружает выбранный рецепт в список виджета
    def load_recipe_by_id(self, recipe_id):
        for i in range(self.recipe_list.count()):
            item = self.recipe_list.item(i)
            if item.data(Qt.UserRole) == recipe_id:
                self.recipe_list.setCurrentItem(item)
                self.load_recipe(item)
                break
    #Загружает данные рецепта из базы данных
    def load_recipe(self, item):
        try:
            recipe_id = item.data(Qt.UserRole)
            self.selected_recipe_id = recipe_id
            recipe = self.processor.get_recipe(recipe_id)
            if recipe:
                self.recipe_name.setText(recipe['name'])
                self.recipe_text.setPlainText(recipe['text'])
                self.current_ingredients = recipe['ingredients']
                self.update_ingredients_list()
                self.load_ingredient_quantities()
        except Exception as e:
            print(f"Error loading recipe: {e}")
    #Загружает количества ингредиентов и заполняет таблицу
    def load_ingredient_quantities(self):
        if self.selected_recipe_id:
            quantities = self.processor.get_ingredient_quantities(self.selected_recipe_id)
            for i in range(self.ingredients_table.rowCount()):
                ingredient_item = self.ingredients_table.item(i, 0)
                if ingredient_item:
                    ingredient = ingredient_item.text()
                    quantity = quantities.get(ingredient, "")
                    self.ingredients_table.setItem(i, 1, QTableWidgetItem(quantity))
    #Обновляет таблицу ингредиентов в базе данных
    def update_ingredients_list(self):
        self.ingredients_table.setRowCount(len(self.current_ingredients))
        for row, ingredient in enumerate(self.current_ingredients):
            self.ingredients_table.setItem(row, 0, QTableWidgetItem(ingredient))
            self.ingredients_table.setItem(row, 1, QTableWidgetItem(""))
    #Предупреждает пользователя о замене всех ингредиентов, ищет ингредиенты при помощи нейронной сети, сохраняет результаты в базе данных
    def extract_ingredients(self):
        text = self.recipe_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, сначала введите текст рецепта")
            return
        if self.current_ingredients:
            reply = QMessageBox.question(
                self, 'Подтвердите Перезапись',
                "Это перезапишет ваш текущий список ингредиентов. Продолжить?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        try:
            extracted = self.processor.extract_ingredients(text)
            self.current_ingredients = extracted
            self.update_ingredients_list()
            if self.selected_recipe_id and extracted:
                self.processor.update_recipe(
                    self.selected_recipe_id,
                    self.recipe_name.text().strip(),
                    text,
                    extracted
                )
                self.statusBar().showMessage(
                    f"Извлечено и сохранено {len(extracted)} ингредиентов",
                    3000
                )
            else:
                self.statusBar().showMessage(
                    f"Извлечено {len(extracted)} ингредиентов",
                    3000
                )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось извлечь ингредиенты: {str(e)}")
    #Осуществляет сохранение рецептов
    def save_recipe(self):
        name = self.recipe_name.text().strip()
        text = self.recipe_text.toPlainText().strip()
        if not name or not text:
            QMessageBox.warning(self, "Предупреждение", "Требуется имя и текст рецепта")
            return
        quantities = {}
        for i in range(self.ingredients_table.rowCount()):
            ingredient_item = self.ingredients_table.item(i, 0)
            quantity_item = self.ingredients_table.item(i, 1)
            if ingredient_item:
                ingredient = ingredient_item.text()
                quantity = quantity_item.text() if quantity_item else ""
                quantities[ingredient] = quantity
        try:
            if self.selected_recipe_id is not None:
                old_recipe = self.processor.get_recipe(self.selected_recipe_id)
                if old_recipe:
                    old_name = old_recipe['name']
                    reply = QMessageBox.question(
                        self, 'Подтвердите Обновление',
                        f"Вы уверены, что хотите обновить '{old_name}' на '{name}'?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        self.processor.update_recipe(
                            self.selected_recipe_id,
                            name,
                            text,
                            self.current_ingredients
                        )
                        self.processor.update_ingredient_quantities(
                            self.selected_recipe_id,
                            quantities
                        )
                        self.statusBar().showMessage("Рецепт успешно обновлен", 3000)
                else:
                    reply = QMessageBox.question(
                        self, 'Создать новый рецепт',
                        "Выбранный рецепт не существует. Создать новый?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        new_id = self.processor.create_recipe(name, text, self.current_ingredients)
                        self.processor.update_ingredient_quantities(
                            new_id,
                            quantities
                        )
                        self.selected_recipe_id = new_id
                        self.statusBar().showMessage("Рецепт успешно создан", 3000)
            else:
                reply = QMessageBox.question(
                    self, 'Подтвердите Новый Рецепт',
                    "Создать новый рецепт?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    new_id = self.processor.create_recipe(name, text, self.current_ingredients)
                    self.processor.update_ingredient_quantities(
                        new_id,
                        quantities
                    )
                    self.selected_recipe_id = new_id
                    self.statusBar().showMessage("Рецепт успешно создан", 3000)
            self.load_recipes()
            if self.selected_recipe_id:
                for i in range(self.recipe_list.count()):
                    item = self.recipe_list.item(i)
                    if item.data(Qt.UserRole) == self.selected_recipe_id:
                        self.recipe_list.setCurrentItem(item)
                        break
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить рецепт: {str(e)}")
    #Удаляет рецепт после подтверждения, удаляет связанное изображение
    def delete_recipe(self):
        current_item = self.recipe_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите рецепт для удаления")
            return
        recipe_id = current_item.data(Qt.UserRole)
        widget = self.recipe_list.itemWidget(current_item)
        recipe_name = "Неизвестно"
        if widget:
            name_label = widget.findChild(QLabel, "name_label")
            if name_label:
                recipe_name = name_label.text()
        img_path = self.get_recipe_image_path(recipe_id)
        if os.path.exists(img_path):
            os.remove(img_path)
        reply = QMessageBox.question(
            self, 'Подтвердите Удаление',
            f"Вы уверены, что хотите удалить рецепт '{recipe_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.processor.delete_recipe(recipe_id)
                self.load_recipes()
                self.recipe_name.clear()
                self.recipe_text.clear()
                self.ingredients_table.clearContents()
                self.ingredients_table.setRowCount(0)
                self.current_ingredients = []
                self.statusBar().showMessage("Рецепт удален", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить рецепт: {str(e)}")
    #Создаёт новый шаблон рецепта
    def add_new_recipe(self):
        new_recipe_id = self.processor.create_recipe(f"Рецепт ", f"Рецепт ")
        recipe_name = f"Рецепт {new_recipe_id}"
        self.processor.update_recipe(new_recipe_id, recipe_name, recipe_name)
        self.load_recipes()
        for i in range(self.recipe_list.count()):
            item = self.recipe_list.item(i)
            if item.data(Qt.UserRole) == new_recipe_id:
                self.recipe_list.setCurrentItem(item)
                self.load_recipe(item)
                break
    #Создаёт диалог для добавления ингредиента, добавляет новый ингредиент
    def add_ingredient(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить Ингредиент")
        layout = QVBoxLayout(dialog)
        name_label = QLabel("Название ингредиента:")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Обязательное поле")
        layout.addWidget(name_label)
        layout.addWidget(name_input)
        quantity_label = QLabel("Количество:")
        quantity_input = QLineEdit()
        quantity_input.setPlaceholderText("Необязательное поле")
        layout.addWidget(quantity_label)
        layout.addWidget(quantity_input)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setEnabled(False)
        name_input.textChanged.connect(lambda: ok_button.setEnabled(bool(name_input.text().strip())))
        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            quantity = quantity_input.text().strip()
            row_position = self.ingredients_table.rowCount()
            self.ingredients_table.insertRow(row_position)
            self.ingredients_table.setItem(row_position, 0, QTableWidgetItem(name))
            self.ingredients_table.setItem(row_position, 1, QTableWidgetItem(quantity))
            self.current_ingredients.append(name)
            if self.selected_recipe_id:
                try:
                    quantities = {}
                    for i in range(self.ingredients_table.rowCount()):
                        ingredient_item = self.ingredients_table.item(i, 0)
                        quantity_item = self.ingredients_table.item(i, 1)
                        if ingredient_item:
                            ingredient = ingredient_item.text()
                            quantity = quantity_item.text() if quantity_item else ""
                            quantities[ingredient] = quantity
                    self.processor.update_recipe_ingredients(
                        self.selected_recipe_id,
                        self.current_ingredients
                    )
                    self.processor.update_ingredient_quantities(
                        self.selected_recipe_id,
                        quantities
                    )
                    self.statusBar().showMessage(f"Ингредиент {name} добавлен", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения: {str(e)}")
    #Аналогичен add_ingredient, но для обновления ингредиентов
    def edit_ingredient(self):
        selected_items = self.ingredients_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите ингредиент для редактирования")
            return
        selected_row = selected_items[0].row()
        old_name = self.ingredients_table.item(selected_row, 0).text()
        old_quantity = self.ingredients_table.item(selected_row, 1).text() if self.ingredients_table.item(selected_row,1) else ""
        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать Ингредиент")
        layout = QVBoxLayout(dialog)
        name_label = QLabel("Название ингредиента:")
        name_input = QLineEdit(old_name)
        name_input.setPlaceholderText("Обязательное поле")
        layout.addWidget(name_label)
        layout.addWidget(name_input)
        quantity_label = QLabel("Количество:")
        quantity_input = QLineEdit(old_quantity)
        quantity_input.setPlaceholderText("Необязательное поле")
        layout.addWidget(quantity_label)
        layout.addWidget(quantity_input)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setEnabled(True)
        name_input.textChanged.connect(lambda: ok_button.setEnabled(bool(name_input.text().strip())))
        if dialog.exec() == QDialog.Accepted:
            new_name = name_input.text().strip()
            new_quantity = quantity_input.text().strip()
            self.ingredients_table.item(selected_row, 0).setText(new_name)
            self.ingredients_table.item(selected_row, 1).setText(new_quantity)
            self.current_ingredients[selected_row] = new_name
            if self.selected_recipe_id:
                try:
                    quantities = {}
                    for i in range(self.ingredients_table.rowCount()):
                        ingredient_item = self.ingredients_table.item(i, 0)
                        quantity_item = self.ingredients_table.item(i, 1)
                        if ingredient_item:
                            ingredient = ingredient_item.text()
                            quantity = quantity_item.text() if quantity_item else ""
                            quantities[ingredient] = quantity
                    self.processor.update_recipe_ingredients(
                        self.selected_recipe_id,
                        self.current_ingredients
                    )
                    self.processor.update_ingredient_quantities(
                        self.selected_recipe_id,
                        quantities
                    )
                    self.statusBar().showMessage("Ингредиент отредактирован и изменения сохранены", 3000)
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения: {str(e)}")
    #Удаляет ингредиенты
    def remove_ingredients(self):
        selected_rows = set()
        for item in self.ingredients_table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите ингредиенты для удаления")
            return
        ingredients_to_remove = []
        for row in selected_rows:
            ingredient_item = self.ingredients_table.item(row, 0)
            if ingredient_item:
                ingredients_to_remove.append(ingredient_item.text())
        reply = QMessageBox.question(
            self,
            'Подтвердите Удаление',
            f"Вы уверены, что хотите удалить эти ингредиенты?\n\n" +
            "\n".join(f"• {ingredient}" for ingredient in ingredients_to_remove),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
        rows = sorted(selected_rows, reverse=True)
        for row in rows:
            self.ingredients_table.removeRow(row)
            del self.current_ingredients[row]
        if self.selected_recipe_id:
            try:
                self.processor.update_recipe_ingredients(
                    self.selected_recipe_id,
                    self.current_ingredients
                )
                self.statusBar().showMessage(
                    f"Удалено {len(rows)} ингредиентов и изменения сохранены",
                    3000
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить изменения: {str(e)}")
        else:
            self.statusBar().showMessage(
                f"Удалено {len(rows)} ингредиентов",
                3000
            )
    #Открывает окно для заказа, передает ему текущий список ингредиентов
    def order_ingredients(self):
        if not self.current_ingredients:
            QMessageBox.information(self, "Заказать Ингредиенты", "Нет ингредиентов для заказа.")
            return
        if hasattr(self, 'order_window') and self.order_window:
            self.order_window.yandex_food.update_ingredients(self.current_ingredients)
            self.order_window.show()
            self.order_window.raise_()
            self.order_window.activateWindow()
        else:
            from ordering import MainWindow
            self.order_window = MainWindow(self.current_ingredients)
            self.order_window.show()
        self.statusBar().showMessage(
            f"Готов к заказу {len(self.current_ingredients)} ингредиентов",
            3000
        )
    #Выполняет поиск рецептов по категориям и по названиям, динамически обновляет список
    def search_recipes(self, text):
        results = self.processor.search_recipes(text)
        self.recipe_list.clear()
        for recipe_id, name in results:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, recipe_id)
            img_path = self.get_recipe_image_path(recipe_id)
            if not os.path.exists(img_path):
                img_path = "content/placeholder_image.png"
            widget = RecipeListItemWidget(name, recipe_id, img_path)
            widget.image_clicked.connect(self.change_recipe_image)
            categories = self.processor.get_recipe_categories(recipe_id)
            for category_id, category_name in categories:
                if category_name not in ["Все"]:
                    widget.add_category_tag(category_name, category_id, lambda cid=category_id: self.remove_recipe_from_category(recipe_id, cid))
            item.setSizeHint(QSize(200, 100))
            self.recipe_list.addItem(item)
            self.recipe_list.setItemWidget(item, widget)
            self.recipe_list.resizeEvent(None)


class RecipeListWidget(QListWidget):
    #Задает некоторые параметры отображения
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeMode(QListWidget.Adjust)
    #Автоматически изменяет размер элементов при изменении размеров окна
    def resizeEvent(self, event):
        width = self.viewport().width() - 20
        for i in range(self.count()):
            item = self.item(i)
            item_widget = self.itemWidget(item)
            if item_widget:
                new_height = min(200, int(width * 0.33))
                item.setSizeHint(QSize(width, new_height))
                item_widget.resize_content(width, new_height)



class QEnhancedTextEdit(QTextEdit):
    #Удаляет html форматы у текста
    def insertFromMimeData(self, mimeData):
        if (mimeData.hasText()):
            text = mimeData.text()
            self.insertPlainText(text)
        else:
            QTextEdit.insertFromMimeData(self, mimeData)



class RecipeListItemWidget(QWidget):
    #Инициализация основных переменных
    image_clicked = Signal(int)
    def __init__(self, name, recipe_id, image_path, parent=None):
        super().__init__(parent)
        self.recipe_id = recipe_id
        self.image_path = image_path
        self.original_pixmap = None
        self.setup_ui(name)
    #Определяет положение элементов виджета
    def setup_ui(self, name):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        self.image_container = QWidget()
        self.image_container.setObjectName("image_container")

        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = ClickableImageLabel(self.recipe_id)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.image_layout.addWidget(self.image_label)

        self.text_container = QWidget()
        self.text_container.setObjectName("text_container")
        self.text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.text_layout = QVBoxLayout(self.text_container)
        self.text_layout.setContentsMargins(5, 5, 5, 5)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("name_label")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.id_label = QLabel(f"ID: {self.recipe_id}")
        self.id_label.setObjectName("id_label")
        self.id_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        self.text_layout.addWidget(self.name_label)
        self.text_layout.addWidget(self.id_label)

        self.categories_scroll_area = QScrollArea()
        self.categories_scroll_area.setWidgetResizable(True)
        self.categories_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.categories_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.categories_widget = QWidget()
        self.categories_widget.setObjectName("categories_widget")
        self.categories_layout = QHBoxLayout(self.categories_widget)
        self.categories_layout.setContentsMargins(0, 0, 0, 0)
        self.categories_layout.setSpacing(5)

        self.categories_scroll_area.setWidget(self.categories_widget)

        self.text_layout.addWidget(self.categories_scroll_area)

        self.layout.addWidget(self.image_container, 1)
        self.layout.addWidget(self.text_container, 2)

        self.load_image()
        self.image_label.clicked.connect(self.on_image_clicked)
    #Автоматически подстраивает размер изображения при изменении размера элемента
    def resize_content(self, width, height):
        image_width = max(100, min(300, int(width * 0.33)))
        self.image_container.setFixedSize(image_width, height)
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaled(
                image_width, height,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            if scaled_pixmap.width() > image_width or scaled_pixmap.height() > height:
                x = (scaled_pixmap.width() - image_width) / 2
                y = (scaled_pixmap.height() - height) / 2
                scaled_pixmap = scaled_pixmap.copy(x, y, image_width, height)
            self.image_label.setPixmap(scaled_pixmap)
    #Загружает изображение рецепта, если оно не задано загружается стандартное изображение
    def load_image(self):
        if not os.path.exists(self.image_path):
            self.image_path = "content/placeholder_image.png"

        self.original_pixmap = QPixmap(self.image_path)
        if not self.original_pixmap.isNull():
            pass
        else:
            self.image_label.setText("Нет Изображения\n(Нажмите, чтобы добавить)")
            self.image_label.setStyleSheet("""
                QLabel {
                    color: #898991;
                    font-size: 12px;
                    qproperty-alignment: AlignCenter;
                }
            """)
    #Получает id рецепта при нажатии на его изображение
    def on_image_clicked(self):
        self.image_clicked.emit(self.recipe_id)
    #Добавляет категории для отображения данного рецепта
    def add_category_tag(self, category_name, category_id, on_close):
        category_frame = QFrame()
        category_frame.setObjectName("category_tag")
        layout = QHBoxLayout(category_frame)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        label = QLabel(category_name)
        label.setObjectName("category_label")
        layout.addWidget(label)
        self.categories_layout.addWidget(category_frame)



class ClickableImageLabel(QLabel):
    clicked = Signal(int)
    def __init__(self, recipe_id, parent=None):
        super().__init__(parent)
        self.recipe_id = recipe_id
        self.setMouseTracking(True)
        self.hovered = False
    #Получаем id рецепта при нажатии на изображение
    def mousePressEvent(self, event):
        self.clicked.emit(self.recipe_id)
        super().mousePressEvent(event)
    #Обработчик события входа курсора в область виджета. Устанавливает флаг hovered и обновляет виджет.
    def enterEvent(self, event):
        self.hovered = True
        self.update_hover_effect()
        super().enterEvent(event)
    #Обработчик события выхода курсора из области виджета. Сбрасывает флаг hovered и обновляет виджет.
    def leaveEvent(self, event):
        self.hovered = False
        self.update_hover_effect()
        super().leaveEvent(event)
    #Задаёт оформление hover-эффекта при наведении на изображение
    def update_hover_effect(self):
        if not self.pixmap():
            return
        if self.hovered:
            overlay = QPixmap(self.pixmap().size())
            overlay.fill(QColor(0, 0, 0, 100))
            hover_pixmap = self.pixmap().copy()
            painter = QPainter(hover_pixmap)
            painter.drawPixmap(0, 0, overlay)
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Qt.white)
            text = "Изменить \nИзображение"
            text_rect = painter.fontMetrics().boundingRect(text)
            text_rect.setHeight(text_rect.height() * 2)
            text_rect.moveCenter(hover_pixmap.rect().center() - QPoint(0, 10))
            painter.drawText(text_rect, Qt.AlignCenter, text)
            painter.end()
            self.setPixmap(hover_pixmap)
        else:
            if hasattr(self.parent().parent(), 'original_pixmap'):
                original_pixmap = self.parent().parent().original_pixmap
                if original_pixmap:
                    current_size = self.size()
                    scaled_pixmap = original_pixmap.scaled(
                        current_size,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    if scaled_pixmap.width() > current_size.width() or scaled_pixmap.height() > current_size.height():
                        x = (scaled_pixmap.width() - current_size.width()) / 2
                        y = (scaled_pixmap.height() - current_size.height()) / 2
                        scaled_pixmap = scaled_pixmap.copy(x, y, current_size.width(), current_size.height())
                    self.setPixmap(scaled_pixmap)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RecipeApp()
    window.show()
    sys.exit(app.exec())
