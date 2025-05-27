import json
import os
from urllib.parse import quote
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QMessageBox,
    QCheckBox
)
from PySide6.QtCore import QUrl, QTimer, Signal, QObject
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from fuzzywuzzy import fuzz

class YandexFoodSignals(QObject):
    cart_clear_warning = Signal(bool)
    login_check_complete = Signal(bool)
    address_check_complete = Signal(bool)
    retailer_selected = Signal(str)
    products_added = Signal(str)
    requirements_met = Signal(bool)
    product_search_status = Signal(str)
    place_slug_obtained = Signal(str)

class YandexFoodOrder(QObject):
    def __init__(self, web_view, main_window, ingredients=None):
        super().__init__()
        self.products = ingredients if ingredients else [
            "Тест"
        ]
        self.web_view = web_view
        self.main_window = main_window
        self.signals = YandexFoodSignals()
        self.current_retailer = None
        self.current_product_index = 0
        self.is_logged_in = False
        self.has_address = False
        self.is_searching = False
        self.place_slug = None
        self.waiting_for_page_load = False

        self.channel = QWebChannel()
        self.channel.registerObject('yandexFoodHelper', self)
        self.web_view.page().setWebChannel(self.channel)
    #Проверяет предупреждение об очистке корзины
    def check_cart_warning(self):
        script = """
        (function() {
            const warning = document.querySelector('[data-testid="modal-desktop-root"]');
            if (!warning) return false;
            const warningText = warning.textContent || "";
            return warningText.includes("очистить корзину") ||
                   warningText.includes("Придётся очистить корзину");
        })()
        """
        self.web_view.page().runJavaScript(script, self.signals.cart_clear_warning.emit)
    #Обновляет ингредиенты
    def update_ingredients(self, ingredients):
        self.products = ingredients if ingredients else []
        self.current_product_index = 0
    #Сбрасывает поиск ингредиентов
    def reset_search(self):
        self.current_product_index = 0
        self.is_searching = False
        self.waiting_for_page_load = False
    #Проверяет, вошёл ли пользователь в аккаунт
    def check_login_status(self):
        script = """
        (function() {
            const loginButton = document.querySelector('[data-testid="desktop-header-profile-button"]');
            if (!loginButton) return true;
            return !(loginButton.textContent || "").includes("Войти");
        })()
        """
        self.web_view.page().runJavaScript(script, self.signals.login_check_complete.emit)
    #Проверяет, указал ли пользователь адрес
    def check_address_selected(self):
        script = """
        (function() {
            const addressRoot = document.querySelector('[data-testid="address-button-root"]');
            if (!addressRoot) return false;
            return !(addressRoot.textContent || "").includes("Укажите адрес доставки");
        })()
        """
        self.web_view.page().runJavaScript(script, self.signals.address_check_complete.emit)
    #Использует обе проверки
    def check_requirements(self):
        self.check_login_status()
        self.check_address_selected()
    #Проверка какой магазин выбрал пользователь
    def get_current_retailer(self):
        script = """
        (function() {
            const url = window.location.href;
            const match = url.match(/\/retail\/([^\/?]+)/);
            return match && match[1] ? match[1] : null;
        })()
        """
        self.web_view.page().runJavaScript(
            script,
            lambda retailer: self.signals.retailer_selected.emit(retailer) if retailer else None
        )
    #Возвращает placeSlug магазина
    def get_place_slug(self):
        script = """
        (function() {
            const url = window.location.href;
            const match = url.match(/placeSlug=([^&]+)/);
            return match && match[1] ? match[1] : null;
        })()
        """
        self.web_view.page().runJavaScript(
            script,
            lambda slug: self.signals.place_slug_obtained.emit(slug) if slug else None
        )
    #Переключает программу на статус поиска, ищет placeSlug выбранного магазина
    def search_products(self, retailer):
        if self.is_searching:
            return
        self.reset_search()
        self.current_retailer = retailer
        self.is_searching = True
        self.signals.product_search_status.emit("Начинаем поиск товаров...")
        self.get_place_slug()
    #Проходит по списку продуктов, выполняет поиск
    def _search_next_product(self):
        if not self.is_searching or self.waiting_for_page_load:
            return
        if self.current_product_index >= len(self.products):
            self.is_searching = False
            if not self.main_window.auto_order_checkbox.isChecked():
                QMessageBox.information(
                    self.main_window,
                    "Заказ завершен",
                    f"Все продукты из списка пройдены"
                )
            self.signals.products_added.emit(self.current_retailer)
            return
        product = self.products[self.current_product_index]
        status = f"[{self.current_product_index + 1}/{len(self.products)}] Поиск: {product}"
        self.signals.product_search_status.emit(status)
        self._search_product(product)
    #Логика поиска товаров
    def _search_product(self, product_name):
        if not self.place_slug:
            self.signals.product_search_status.emit(
                f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Ошибка: placeSlug не найден"
            )
            self.current_product_index += 1
            QTimer.singleShot(1500, self._search_next_product)
            return
        self.waiting_for_page_load = True
        encoded_product = quote(product_name)
        search_url = f"https://eda.yandex.ru/retail/{self.current_retailer}?placeSlug={self.place_slug}&query={encoded_product}"
        self.web_view.setUrl(QUrl(search_url))
        QTimer.singleShot(4000, lambda: self._process_search_results(product_name))
    #Логика добавления товара
    def _add_product_to_cart(self, product, original_name):
        if not self.main_window.auto_order_checkbox.isChecked():
            status_msg = "Пожалуйста, добавьте товар вручную и нажмите 'Следующий товар'"
            self.signals.product_search_status.emit(
                f"[{self.current_product_index + 1}/{len(self.products)}] "
                f"{original_name} - {status_msg}"
            )
            self.main_window.add_products_btn.setText("Следующий товар")
            return
        script = f"""
        (function() {{
            try {{
                const allCards = Array.from(document.querySelectorAll('[data-testid="product-card-root"]'));
                const targetCard = allCards.find(card => card.outerHTML === {json.dumps(product['element'])});

                if (!targetCard) return JSON.stringify({{
                    status: "error",
                    message: "Карточка товара не найдена"
                }});

                const addButton = targetCard.querySelector('[data-testid="amount-select-increment"]');
                if (addButton) {{
                    addButton.click();
                    return JSON.stringify({{
                        status: "added",
                        productName: {json.dumps(product['name'])},
                        price: {json.dumps(product['price'])},
                        weight: {json.dumps(product['weight'])}
                    }});
                }}
                return JSON.stringify({{
                    status: "error",
                    message: "Кнопка добавления не найдена"
                }});
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.message
                }});
            }}
        }})()
        """

        def handle_add_result(json_result):
            try:
                result = json.loads(json_result) if json_result else None
                if result and result.get("status") == "added":
                    status_msg = f"Добавлено: {result['productName']} (Цена: {result['price']}, Вес: {result['weight']})"
                else:
                    error_msg = result.get("message", "Неизвестная ошибка") if result else "Нет результата"
                    status_msg = f"Ошибка: {error_msg}"
                self.signals.product_search_status.emit(
                    f"[{self.current_product_index + 1}/{len(self.products)}] "
                    f"{original_name} - {status_msg}"
                )
                self.current_product_index += 1
                QTimer.singleShot(1500, self._search_next_product)
            except Exception as e:
                self.signals.product_search_status.emit(
                    f"[{self.current_product_index + 1}/{len(self.products)}] "
                    f"{original_name} - Ошибка обработки"
                )
                self.current_product_index += 1
                QTimer.singleShot(1500, self._search_next_product)

        self.web_view.page().runJavaScript(script, handle_add_result)
    #Обрабатывает поисковые результаты, находит названия, стоимость и вес каждого товара
    def _process_search_results(self, product_name):
        self.waiting_for_page_load = False
        normalized_query = self._normalize_name(product_name)
        script = """
        (function() {
            try {
                const cards = Array.from(document.querySelectorAll('[data-testid="product-card-root"]'));
                if (cards.length === 0) return JSON.stringify({status: "empty"});

                const results = cards.map((card) => {
                    const nameElement = card.querySelector('[data-testid="product-card-name"]');
                    const priceElement = card.querySelector('[data-testid="product-card-price"]');
                    const weightElement = card.querySelector('[data-testid="product-card-weight"]');

                    return {
                        name: nameElement ? nameElement.textContent.trim() : "Неизвестно",
                        priceText: priceElement ? priceElement.textContent.trim() : "0 ₽",
                        weightText: weightElement ? weightElement.textContent.trim() : "",
                        element: card.outerHTML
                    };
                });

                return JSON.stringify({status: "success", products: results});
            } catch (e) {
                return JSON.stringify({status: "error", message: e.message});
            }
        })()
        """
        #Возвращает числовое значение цены
        def parse_price(price_str):
            try:
                cleaned = price_str.replace(' ', '').replace('₽', '').replace(',', '.').strip()
                return float(cleaned) if cleaned else 0
            except:
                return 0
        #Возвращает числовое значение веса товара, вес приводится к одним единицам измерения
        def parse_weight(weight_str):
            try:
                num_str = ''.join(c for c in weight_str.split()[0] if c.isdigit() or c == '.')
                if not num_str:
                    return 0
                weight = float(num_str)
                if 'кг' in weight_str.lower():
                    weight *= 1000
                elif 'л' in weight_str.lower() and not ('г' in weight_str.lower() or 'мл' in weight_str.lower()):
                    weight *= 1000
                return weight
            except:
                return 0
        #Логика обработки полученных результатов, добавление рейтинга каждого товара и поиск лучшего варианта
        def handle_result(json_result):
            try:
                result = json.loads(json_result) if json_result else None
                if not result or result.get("status") != "success":
                    error_msg = result.get("message", "Неизвестная ошибка") if result else "Нет результата"
                    self.signals.product_search_status.emit(
                        f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Ошибка: {error_msg}"
                    )
                    self.current_product_index += 1
                    QTimer.singleShot(1500, self._search_next_product)
                    return
                products = result.get("products", [])
                if not products:
                    self.signals.product_search_status.emit(
                        f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Товары не найдены"
                    )
                    self.current_product_index += 1
                    QTimer.singleShot(1500, self._search_next_product)
                    return
                valid_products = []
                for product in products:
                    try:
                        price = parse_price(product['priceText'])
                        weight = parse_weight(product['weightText'])
                        product['normalized_name'] = self._normalize_name(product['name'])

                        if price > 0 and weight > 0:
                            product['price'] = price
                            product['weight'] = weight
                            product['value_ratio'] = weight / price
                            valid_products.append(product)
                    except:
                        continue
                if not valid_products:
                    self.signals.product_search_status.emit(
                        f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Нет подходящих товаров"
                    )
                    self.current_product_index += 1
                    QTimer.singleShot(1500, self._search_next_product)
                    return
                best_match = None
                best_score = -1
                for product in valid_products:
                    name_score = fuzz.token_set_ratio(normalized_query, product['normalized_name'])
                    value_score = min(30, product['value_ratio'] * 5)
                    total_score = (name_score * 0.6) + (value_score * 0.4)
                    if total_score > best_score:
                        best_match = product
                        best_score = total_score
                if best_match:
                    self._add_product_to_cart(best_match, product_name)
                else:
                    self.signals.product_search_status.emit(
                        f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Не найдено подходящего"
                    )
                    self.current_product_index += 1
                    QTimer.singleShot(1500, self._search_next_product)
            except Exception as e:
                self.signals.product_search_status.emit(
                    f"[{self.current_product_index + 1}/{len(self.products)}] {product_name} - Ошибка обработки"
                )
                self.current_product_index += 1
                QTimer.singleShot(1500, self._search_next_product)
        self.web_view.page().runJavaScript(script, handle_result)
    #Предобработка полученного названия продукта
    def _normalize_name(self, name):
        if not name:
            return ""
        normalized = name.lower()
        normalized = normalized.replace('ё', 'е')
        normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
        return ' '.join(normalized.split())


class MainWindow(QMainWindow):
    def __init__(self, ingredients=None):
        super().__init__()
        self.setWindowTitle("Создание заказа - Яндекс Еда")
        self.resize(1050, 800)
        self.setMinimumSize(900, 500)
        self.raise_()

        self.web_view = QWebEngineView()
        profile = QWebEngineProfile("yandex_food_profile", self.web_view)
        profile.setPersistentStoragePath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
        self.web_view.setPage(QWebEnginePage(profile, self.web_view))

        self.status_label = QLabel("Инициализация...")
        self.status_label.setStyleSheet("font-size: 14px; padding: 5px;")
        self.status_label.setFixedHeight(30)

        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-size: 14px; padding: 5px; color: #555;")
        self.progress_label.setFixedHeight(30)

        self.auto_order_checkbox = QCheckBox("Автоматически добавлять товары")
        self.auto_order_checkbox.setChecked(True)
        self.auto_order_checkbox.setStyleSheet("font-size: 14px; padding: 5px;")

        self.add_products_btn = QPushButton("Добавить товары в корзину")
        self.add_products_btn.setObjectName("ordering_button")
        self.add_products_btn.setStyleSheet("font-size: 14px; padding: 8px;")
        self.add_products_btn.setFixedHeight(40)
        self.add_products_btn.clicked.connect(self.start_adding_products)
        self.add_products_btn.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.auto_order_checkbox)
        layout.addWidget(self.add_products_btn)
        layout.addWidget(self.web_view)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setStretchFactor(self.web_view, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.yandex_food = YandexFoodOrder(self.web_view, self, ingredients)

        self.yandex_food.signals.login_check_complete.connect(self.on_login_check)
        self.yandex_food.signals.address_check_complete.connect(self.on_address_check)
        self.yandex_food.signals.retailer_selected.connect(self.on_retailer_selected)
        self.yandex_food.signals.products_added.connect(self.on_products_added)
        self.yandex_food.signals.requirements_met.connect(self.on_requirements_met)
        self.yandex_food.signals.product_search_status.connect(self.update_progress)
        self.yandex_food.signals.place_slug_obtained.connect(self.on_place_slug_obtained)
        self.yandex_food.signals.cart_clear_warning.connect(self.on_cart_warning)
        self.web_view.urlChanged.connect(self.on_url_changed)

        self.is_logged_in = False
        self.has_address = False
        self.current_retailer = None

        self.web_view.setUrl(QUrl("https://eda.yandex.ru"))
        QTimer.singleShot(3000, self.start_monitoring)
    #Предупреждение очистить корзину
    def on_cart_warning(self, warning_present):
        if warning_present:
            self.status_label.setText("Внимание: Нужно очистить корзину! Сделайте это вручную.")
            self.add_products_btn.setEnabled(False)

            if self.yandex_food.is_searching:
                self.stop_adding_products()
                QMessageBox.warning(
                    self,
                    "Предупреждение о корзине",
                    "Необходимо очистить корзину перед продолжением.\n"
                    "Сделайте это вручную и попробуйте снова."
                )
    #Выполняет первоначальные проверки
    def start_monitoring(self):
        self.status_label.setText("Проверка требований...")
        self.yandex_food.check_requirements()
    #Начинает логику поиска товаров
    def start_adding_products(self):
        if self.yandex_food.is_searching:
            if not self.auto_order_checkbox.isChecked():
                self.yandex_food.current_product_index += 1
                if self.yandex_food.current_product_index >= len(self.yandex_food.products):
                    self.stop_adding_products()
                else:
                    QTimer.singleShot(100, self.yandex_food._search_next_product)
            else:
                self.stop_adding_products()
        else:
            if not self.current_retailer:
                self.status_label.setText("Сначала выберите магазин")
                return
            self.status_label.setText(f"Поиск товаров в {self.current_retailer}...")
            self.progress_label.clear()
            self.add_products_btn.setText(
                "Остановить" if self.auto_order_checkbox.isChecked() else "Следующий товар")
            self.yandex_food.search_products(self.current_retailer)
    #Прекращает поиск товаров
    def stop_adding_products(self):
        self.yandex_food.reset_search()
        if self.current_retailer:
            self.status_label.setText(f"Выбран магазин: {self.current_retailer}")
        else:
            self.status_label.setText("Готово - выберите магазин")
        self.add_products_btn.setText("Добавить товары в корзину")
        self.add_products_btn.setEnabled(True)
    #Задаёт текст в поле статуса
    def update_progress(self, message):
        self.progress_label.setText(message)
    #Проверка требований после входа
    def on_login_check(self, is_logged_in):
        self.is_logged_in = is_logged_in
        self.yandex_food.is_logged_in = is_logged_in
        self.check_requirements_met()
    #Проверка требований после ввода адреса
    def on_address_check(self, has_address):
        self.has_address = has_address
        self.yandex_food.has_address = has_address
        self.check_requirements_met()
    #Проверяет одновременное выполнение условий
    def check_requirements_met(self):
        if self.is_logged_in and self.has_address:
            self.yandex_food.signals.requirements_met.emit(True)
        else:
            self.yandex_food.signals.requirements_met.emit(False)
    #Предлагает выбрать магазин
    def on_requirements_met(self, met):
        if met:
            self.status_label.setText("Готово - выберите магазин")
            self.yandex_food.get_current_retailer()
        else:
            if not self.is_logged_in:
                self.status_label.setText("Пожалуйста, войдите в систему")
            elif not self.has_address:
                self.status_label.setText("Пожалуйста, укажите адрес доставки")
            self.add_products_btn.setEnabled(False)
    #Выполняет основные проверки при изменении url
    def on_url_changed(self, url):
        self.yandex_food.check_login_status()
        self.yandex_food.check_cart_warning()
        self.check_requirements_met()
        self.yandex_food.check_cart_warning()
        url_str = url.toString()
        if self.is_logged_in and self.has_address and "/retail/" in url_str:
            self.yandex_food.get_current_retailer()
            self.yandex_food.get_place_slug()
        else:
            self.stop_adding_products()
            self.current_retailer = None
            self.add_products_btn.setEnabled(False)
            if self.is_logged_in and self.has_address:
                self.status_label.setText("Пожалуйста, выберите магазин")
    #Изменяет статус, сбрасывает поиск, делает кнопку активной
    def stop_adding_products(self):
        self.yandex_food.reset_search()
        if self.current_retailer:
            self.status_label.setText(f"Выбран магазин: {self.current_retailer}")
        else:
            self.status_label.setText("Готово - выберите магазин")
        self.add_products_btn.setText("Добавить товары в корзину")
        self.add_products_btn.setEnabled(True)
    #Делает кнопку активной если выбран магазин, отображает в статусе магазин
    def on_retailer_selected(self, retailer):
        if retailer:
            self.current_retailer = retailer
            self.status_label.setText(f"Выбран: {retailer}")
            self.add_products_btn.setEnabled(True)
        else:
            self.current_retailer = None
            self.add_products_btn.setEnabled(False)
            if self.is_logged_in and self.has_address:
                self.status_label.setText("Пожалуйста, выберите магазин")
    #Инициализирует поиск следующего продукта если стоит флаг поиска и страница не в процессе загрузки
    def on_place_slug_obtained(self, place_slug):
        self.yandex_food.place_slug = place_slug
        if self.yandex_food.is_searching and not self.yandex_food.waiting_for_page_load:
            QTimer.singleShot(2000, self.yandex_food._search_next_product)
    #Статус о завершении добавления продуктов
    def on_products_added(self, retailer):
        self.status_label.setText(f"Завершено добавление в {retailer}")
        self.add_products_btn.setText("Добавить товары в корзину")
        self.add_products_btn.setEnabled(True)
        QMessageBox.information(self, "Завершено", "Все товары добавлены в корзину")

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
