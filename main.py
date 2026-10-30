import tkinter as tk
from tkinter import ttk, messagebox
import json
import random
from datetime import datetime, timedelta
import threading
import time

from rules_engine import find_conflicts, rule_matches, rules_conflict


class SmartHomeController:
    def __init__(self, root):
        self.root = root
        self.root.title("🏠 Контроллер умного дома")
        self.root.geometry("1200x750")

        # данные
        self.rules = []
        self.sensors = {}
        self.log = []
        self.simulation_active = False
        self.active_timers = []  # список активных таймеров
        self.active_actions = {}  # словарь активных действий: device -> действие

        self.timer_lock = threading.Lock()  # блокировка для потокобезопасности

        self.initialize_sensors()  # инициализация датчиков

        self.create_widgets()  # создание интерфейса

        self.load_rules()  # загрузка правил

        self.start_simulation()  # запуск симуляции

        self.start_timer_checker()  # запуск проверки таймеров

    def initialize_sensors(self):
        """Инициализация начальных значений датчиков"""
        self.sensors = {
            "temperature": round(random.uniform(18, 30), 1),
            "humidity": round(random.uniform(30, 80), 1),
            "light": random.randint(0, 100),
            "motion": random.choice([True, False])
        }
        self.time_of_day = self.get_time_of_day()

    def get_time_of_day(self):
        """Определение времени суток"""
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "утро"
        elif 12 <= hour < 18:
            return "день"
        elif 18 <= hour < 23:
            return "вечер"
        else:
            return "ночь"

    def create_widgets(self):
        """Создание интерфейса"""
        # notebook для вкладок
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # вкладка правил
        self.rules_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rules_frame, text="📋 Правила")
        self.create_rules_tab()

        # вкладка датчиков
        self.sensors_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sensors_frame, text="🌡️ Датчики")
        self.create_sensors_tab()

        # вкладка лога
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="📝 Лог действий")
        self.create_log_tab()

        # вкладка таймеров
        self.timers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timers_frame, text="⏱️ Таймеры")
        self.create_timers_tab()

    def create_rules_tab(self):
        """Создание вкладки с правилами"""
        # главный горизонтальный контейнер
        main_paned = ttk.PanedWindow(self.rules_frame, orient='horizontal')
        main_paned.pack(fill='both', expand=True)

        # левая панель - добавление правил
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        # правая панель - активные действия
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # левая часть: добавление правил
        add_frame = ttk.LabelFrame(left_frame, text="Добавить новое правило", padding=10)
        add_frame.pack(fill='x', padx=5, pady=5)

        # устройство
        ttk.Label(add_frame, text="Устройство:").grid(row=0, column=0, sticky='w', pady=5)
        self.device_var = tk.StringVar(value="кондиционер")
        device_combo = ttk.Combobox(add_frame, textvariable=self.device_var,
                                    values=["кондиционер", "обогреватель", "освещение", "вентилятор", "сигнализация"])
        device_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=5)

        # действие
        ttk.Label(add_frame, text="Действие:").grid(row=1, column=0, sticky='w', pady=5)
        self.action_var = tk.StringVar(value="включить")
        action_combo = ttk.Combobox(add_frame, textvariable=self.action_var,
                                    values=["включить", "выключить"])
        action_combo.grid(row=1, column=1, sticky='ew', pady=5, padx=5)

        # таймер
        ttk.Label(add_frame, text="Таймер (минут):").grid(row=2, column=0, sticky='w', pady=5)
        timer_frame = ttk.Frame(add_frame)
        timer_frame.grid(row=2, column=1, sticky='ew', pady=5)
        self.timer_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(timer_frame, text="Использовать", variable=self.timer_enabled,
                        command=self.toggle_timer).pack(side='left')
        self.timer_value = tk.StringVar(value="30")
        self.timer_entry = ttk.Entry(timer_frame, textvariable=self.timer_value, width=8, state='disabled')
        self.timer_entry.pack(side='left', padx=5)
        ttk.Label(timer_frame, text="мин").pack(side='left')

        # условия с чекбоксами
        ttk.Label(add_frame, text="Условия (отметьте нужные):").grid(row=3, column=0, columnspan=2, sticky='w', pady=10)

        conditions_frame = ttk.Frame(add_frame)
        conditions_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)

        # температура
        self.use_temp = tk.BooleanVar(value=False)
        temp_check = ttk.Checkbutton(conditions_frame, text="Температура", variable=self.use_temp,
                                     command=lambda: self.toggle_condition('temp'))
        temp_check.grid(row=0, column=0, sticky='w', pady=2)

        self.temp_operator = tk.StringVar(value=">")
        self.temp_op_menu = ttk.OptionMenu(conditions_frame, self.temp_operator, ">", ">", "<", "=", ">=", "<=")
        self.temp_op_menu.grid(row=0, column=1, padx=2)
        self.temp_value = tk.StringVar(value="24")
        self.temp_entry = ttk.Entry(conditions_frame, textvariable=self.temp_value, width=5)
        self.temp_entry.grid(row=0, column=2, padx=2)
        ttk.Label(conditions_frame, text="°C").grid(row=0, column=3, sticky='w')

        self.toggle_condition_widgets('temp', False)

        # влажность
        self.use_hum = tk.BooleanVar(value=False)
        hum_check = ttk.Checkbutton(conditions_frame, text="Влажность", variable=self.use_hum,
                                    command=lambda: self.toggle_condition('hum'))
        hum_check.grid(row=1, column=0, sticky='w', pady=2)

        self.hum_operator = tk.StringVar(value=">")
        self.hum_op_menu = ttk.OptionMenu(conditions_frame, self.hum_operator, ">", ">", "<", "=", ">=", "<=")
        self.hum_op_menu.grid(row=1, column=1, padx=2)
        self.hum_value = tk.StringVar(value="50")
        self.hum_entry = ttk.Entry(conditions_frame, textvariable=self.hum_value, width=5)
        self.hum_entry.grid(row=1, column=2, padx=2)
        ttk.Label(conditions_frame, text="%").grid(row=1, column=3, sticky='w')

        self.toggle_condition_widgets('hum', False)

        # освещённость
        self.use_light = tk.BooleanVar(value=False)
        light_check = ttk.Checkbutton(conditions_frame, text="Освещённость", variable=self.use_light,
                                      command=lambda: self.toggle_condition('light'))
        light_check.grid(row=2, column=0, sticky='w', pady=2)

        self.light_operator = tk.StringVar(value=">")
        self.light_op_menu = ttk.OptionMenu(conditions_frame, self.light_operator, ">", ">", "<", "=", ">=", "<=")
        self.light_op_menu.grid(row=2, column=1, padx=2)
        self.light_value = tk.StringVar(value="30")
        self.light_entry = ttk.Entry(conditions_frame, textvariable=self.light_value, width=5)
        self.light_entry.grid(row=2, column=2, padx=2)

        self.toggle_condition_widgets('light', False)

        # время суток
        self.use_time = tk.BooleanVar(value=False)
        time_check = ttk.Checkbutton(conditions_frame, text="Время суток", variable=self.use_time,
                                     command=lambda: self.toggle_condition('time'))
        time_check.grid(row=3, column=0, sticky='w', pady=2)

        self.time_var = tk.StringVar(value="вечер")
        self.time_combo = ttk.Combobox(conditions_frame, textvariable=self.time_var,
                                       values=["утро", "день", "вечер", "ночь"], state='disabled')
        self.time_combo.grid(row=3, column=1, columnspan=3, sticky='ew', pady=2)

        # движение
        self.use_motion = tk.BooleanVar(value=False)
        motion_check = ttk.Checkbutton(conditions_frame, text="Движение", variable=self.use_motion,
                                       command=lambda: self.toggle_condition('motion'))
        motion_check.grid(row=4, column=0, sticky='w', pady=2)

        self.motion_var = tk.StringVar(value="есть")
        self.motion_combo = ttk.Combobox(conditions_frame, textvariable=self.motion_var,
                                         values=["есть", "нет"], state='disabled')
        self.motion_combo.grid(row=4, column=1, columnspan=3, sticky='ew', pady=2)

        # кнопка добавления
        ttk.Button(add_frame, text="✅ Добавить правило", command=self.add_rule).grid(row=5, column=0, columnspan=2,
                                                                                     pady=10)

        # список правил
        list_frame = ttk.LabelFrame(left_frame, text="Текущие правила", padding=10)
        list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # treeview для правил
        columns = ("ID", "Устройство", "Условия", "Действие", "Таймер")
        self.rules_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.rules_tree.heading(col, text=col)
            self.rules_tree.column(col, width=100)

        self.rules_tree.pack(side='left', fill='both', expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.rules_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.rules_tree.configure(yscrollcommand=scrollbar.set)

        # кнопки управления правилами
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(btn_frame, text="🗑️ Удалить", command=self.delete_selected_rule).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="🔄 Обновить", command=self.update_rules_list).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="🔍 Конфликты", command=self.check_conflicts).pack(side='left', padx=2)

        # правая часть: активные действия
        active_frame = ttk.LabelFrame(right_frame, text="📊 Активные устройства", padding=10)
        active_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # заголовок с текущим временем
        self.active_time_label = ttk.Label(active_frame, text="", font=('Arial', 10))
        self.active_time_label.pack(pady=5)

        # разделительная линия
        ttk.Separator(active_frame, orient='horizontal').pack(fill='x', pady=5)

        # фрейм для статуса устройств
        self.devices_status_frame = ttk.Frame(active_frame)
        self.devices_status_frame.pack(fill='both', expand=True, pady=10)

        # создаём индикаторы для всех устройств
        self.device_indicators = {}
        devices = ["кондиционер", "обогреватель", "освещение", "вентилятор", "сигнализация"]
        device_icons = {
            "кондиционер": "❄️",
            "обогреватель": "🔥",
            "освещение": "💡",
            "вентилятор": "🌀",
            "сигнализация": "🚨"
        }

        for device in devices:
            device_frame = ttk.Frame(self.devices_status_frame)
            device_frame.pack(fill='x', pady=5)

            icon_label = ttk.Label(device_frame, text=device_icons[device], font=('Arial', 20))
            icon_label.pack(side='left', padx=10)

            name_label = ttk.Label(device_frame, text=device.capitalize(), font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)

            status_label = ttk.Label(device_frame, text="⚪ Не активно", font=('Arial', 11))
            status_label.pack(side='right', padx=10)

            self.device_indicators[device] = status_label

        # кнопка обновления статуса
        ttk.Button(active_frame, text="🔄 Обновить статус",
                   command=self.update_active_actions_display).pack(pady=10)

        # обновляем списки
        self.update_rules_list()
        self.update_active_actions_display()

    def toggle_timer(self):
        """Включение/выключение поля таймера"""
        if self.timer_enabled.get():
            self.timer_entry.config(state='normal')
        else:
            self.timer_entry.config(state='disabled')

    def toggle_condition(self, condition_type):
        """Включение/выключение условий при отметке чекбокса"""
        if condition_type == 'temp':
            self.toggle_condition_widgets('temp', self.use_temp.get())
        elif condition_type == 'hum':
            self.toggle_condition_widgets('hum', self.use_hum.get())
        elif condition_type == 'light':
            self.toggle_condition_widgets('light', self.use_light.get())
        elif condition_type == 'time':
            self.time_combo.config(state='readonly' if self.use_time.get() else 'disabled')
        elif condition_type == 'motion':
            self.motion_combo.config(state='readonly' if self.use_motion.get() else 'disabled')

    def toggle_condition_widgets(self, condition_type, enabled):
        """Переключение состояния виджетов условий"""
        state = 'normal' if enabled else 'disabled'
        if condition_type == 'temp':
            self.temp_op_menu.config(state=state)
            self.temp_entry.config(state=state)
        elif condition_type == 'hum':
            self.hum_op_menu.config(state=state)
            self.hum_entry.config(state=state)
        elif condition_type == 'light':
            self.light_op_menu.config(state=state)
            self.light_entry.config(state=state)

    def create_sensors_tab(self):
        """Создание вкладки с датчиками"""
        # текущие показания
        values_frame = ttk.LabelFrame(self.sensors_frame, text="Текущие показания", padding=20)
        values_frame.pack(fill='x', padx=10, pady=10)

        # датчики
        self.temp_label = ttk.Label(values_frame, text="🌡️ Температура: -- °C", font=('Arial', 14))
        self.temp_label.pack(anchor='w', pady=5)

        self.hum_label = ttk.Label(values_frame, text="💧 Влажность: -- %", font=('Arial', 14))
        self.hum_label.pack(anchor='w', pady=5)

        self.light_label = ttk.Label(values_frame, text="💡 Освещённость: --", font=('Arial', 14))
        self.light_label.pack(anchor='w', pady=5)

        self.motion_label = ttk.Label(values_frame, text="🏃 Движение: --", font=('Arial', 14))
        self.motion_label.pack(anchor='w', pady=5)

        self.time_label = ttk.Label(values_frame, text="🕐 Время суток: --", font=('Arial', 14))
        self.time_label.pack(anchor='w', pady=5)

        # управление симуляцией
        control_frame = ttk.LabelFrame(self.sensors_frame, text="Управление симуляцией", padding=10)
        control_frame.pack(fill='x', padx=10, pady=10)

        self.sim_button = ttk.Button(control_frame, text="⏸️ Остановить симуляцию",
                                     command=self.toggle_simulation)
        self.sim_button.pack(side='left', padx=5)

        ttk.Button(control_frame, text="🔄 Обновить показания",
                   command=self.update_sensor_display).pack(side='left', padx=5)

        ttk.Button(control_frame, text="▶️ Проверить правила",
                   command=self.check_rules).pack(side='left', padx=5)

        # ручное управление ВСЕМИ датчиками
        manual_frame = ttk.LabelFrame(self.sensors_frame, text="Ручная установка значений", padding=10)
        manual_frame.pack(fill='x', padx=10, pady=10)

        # температура
        ttk.Label(manual_frame, text="Температура (°C):").grid(row=0, column=0, pady=5, padx=5, sticky='w')
        self.manual_temp = tk.DoubleVar(value=24.0)
        temp_scale = ttk.Scale(manual_frame, from_=15, to=35, variable=self.manual_temp,
                               orient='horizontal', length=200, command=self.on_temp_scale_change)
        temp_scale.grid(row=0, column=1, padx=5)
        self.manual_temp_label = ttk.Label(manual_frame, text="24.0", width=5)
        self.manual_temp_label.grid(row=0, column=2, padx=5)

        # влажность
        ttk.Label(manual_frame, text="Влажность (%):").grid(row=1, column=0, pady=5, padx=5, sticky='w')
        self.manual_hum = tk.DoubleVar(value=50.0)
        hum_scale = ttk.Scale(manual_frame, from_=20, to=90, variable=self.manual_hum,
                              orient='horizontal', length=200, command=self.on_hum_scale_change)
        hum_scale.grid(row=1, column=1, padx=5)
        self.manual_hum_label = ttk.Label(manual_frame, text="50.0", width=5)
        self.manual_hum_label.grid(row=1, column=2, padx=5)

        # освещённость
        ttk.Label(manual_frame, text="Освещённость:").grid(row=2, column=0, pady=5, padx=5, sticky='w')
        self.manual_light = tk.IntVar(value=50)
        light_scale = ttk.Scale(manual_frame, from_=0, to=100, variable=self.manual_light,
                                orient='horizontal', length=200, command=self.on_light_scale_change)
        light_scale.grid(row=2, column=1, padx=5)
        self.manual_light_label = ttk.Label(manual_frame, text="50", width=5)
        self.manual_light_label.grid(row=2, column=2, padx=5)

        # движение
        ttk.Label(manual_frame, text="Движение:").grid(row=3, column=0, pady=5, padx=5, sticky='w')
        self.manual_motion = tk.BooleanVar(value=False)
        ttk.Checkbutton(manual_frame, text="Есть движение", variable=self.manual_motion).grid(row=3, column=1,
                                                                                              sticky='w', padx=5)

        # время суток
        ttk.Label(manual_frame, text="Время суток:").grid(row=4, column=0, pady=5, padx=5, sticky='w')
        self.manual_time = tk.StringVar(value=self.time_of_day)
        time_combo = ttk.Combobox(manual_frame, textvariable=self.manual_time,
                                  values=["утро", "день", "вечер", "ночь"], state='readonly')
        time_combo.grid(row=4, column=1, sticky='w', padx=5)

        ttk.Button(manual_frame, text="Применить все значения",
                   command=self.apply_manual_values).grid(row=5, column=0, columnspan=3, pady=10)

        self.update_sensor_display()

    def on_temp_scale_change(self, value):
        """Обработчик изменения температуры - округление до десятых"""
        rounded = round(float(value), 1)
        self.manual_temp.set(rounded)
        self.manual_temp_label.config(text=f"{rounded:.1f}")

    def on_hum_scale_change(self, value):
        """Обработчик изменения влажности - округление до десятых"""
        rounded = round(float(value), 1)
        self.manual_hum.set(rounded)
        self.manual_hum_label.config(text=f"{rounded:.1f}")

    def on_light_scale_change(self, value):
        """Обработчик изменения освещённости - целые числа"""
        rounded = round(float(value))
        self.manual_light.set(rounded)
        self.manual_light_label.config(text=str(rounded))

    def create_log_tab(self):
        """Создание вкладки с логом"""
        # текстовое поле для лога
        self.log_text = tk.Text(self.log_frame, wrap='word', font=('Courier', 10))
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Кнопки управления логом
        btn_frame = ttk.Frame(self.log_frame)
        btn_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(btn_frame, text="🗑️ Очистить лог", command=self.clear_log).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="💾 Сохранить лог", command=self.save_log).pack(side='left', padx=5)

    def create_timers_tab(self):
        """Создание вкладки с активными таймерами"""
        # заголовок
        ttk.Label(self.timers_frame, text="Активные таймеры устройств",
                  font=('Arial', 14)).pack(pady=10)

        # пояснение
        ttk.Label(self.timers_frame, text="Таймеры продолжают работать независимо от изменения условий!\n"
                                          "После активации таймер не останавливается до истечения времени.",
                  font=('Arial', 10), foreground='gray').pack(pady=5)

        # список таймеров
        self.timers_text = tk.Text(self.timers_frame, wrap='word', font=('Courier', 11), height=15)
        self.timers_text.pack(fill='both', expand=True, padx=10, pady=10)

        # кнопка обновления
        ttk.Button(self.timers_frame, text="🔄 Обновить список таймеров",
                   command=self.update_timers_display).pack(pady=5)

        self.update_timers_display()

    def update_active_actions_display(self):
        """Обновление отображения активных действий"""
        # обновляем время
        current_time = datetime.now().strftime("%H:%M:%S")
        self.active_time_label.config(text=f"🕐 Текущее время: {current_time}")

        # обновляем статус устройств
        for device, indicator in self.device_indicators.items():
            if device in self.active_actions:
                action = self.active_actions[device]
                if action == "включить":
                    indicator.config(text="🟢 Включено", foreground='green')
                else:
                    indicator.config(text="🔴 Выключено", foreground='red')
            else:
                indicator.config(text="⚪ Не активно", foreground='gray')

        # планируем следующее обновление
        self.root.after(1000, self.update_active_actions_display)

    def check_conflicts(self):
        """Проверка конфликтующих правил с возможностью выбора"""
        conflicts = find_conflicts(self.rules)

        if conflicts:
            self.show_conflicts_dialog(conflicts)
        else:
            messagebox.showinfo("Проверка", "Конфликтующие правила не найдены")

    def show_conflicts_dialog(self, conflicts):
        """Диалог для разрешения конфликтов"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔍 Найдены конфликтующие правила")
        dialog.geometry("800x500")

        ttk.Label(dialog, text="Выберите правила для разрешения конфликтов:",
                  font=('Arial', 12)).pack(pady=10)

        # фрейм с прокруткой
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        conflict_vars = []

        for idx, (i, j, common_conditions) in enumerate(conflicts):
            conflict_frame = ttk.LabelFrame(scrollable_frame,
                                            text=f"Конфликт {idx + 1}: {self.rules[i]['device']}",
                                            padding=10)
            conflict_frame.pack(fill='x', pady=5)

            ttk.Label(conflict_frame,
                      text=f"Общие условия: {', '.join(common_conditions) if common_conditions else 'всегда'}",
                      font=('Arial', 10, 'bold')).pack(anchor='w')

            # правило 1
            var1 = tk.BooleanVar(value=True)
            cb1 = ttk.Checkbutton(conflict_frame, text=f"Правило {i + 1}: {self.rule_to_string(self.rules[i])}",
                                  variable=var1)
            cb1.pack(anchor='w', pady=2)

            # правило 2
            var2 = tk.BooleanVar(value=False)
            cb2 = ttk.Checkbutton(conflict_frame, text=f"Правило {j + 1}: {self.rule_to_string(self.rules[j])}",
                                  variable=var2)
            cb2.pack(anchor='w', pady=2)

            conflict_vars.append((i, j, var1, var2))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def resolve_conflicts():
            rules_to_remove = set()
            for i, j, var1, var2 in conflict_vars:
                if var1.get() and not var2.get():
                    rules_to_remove.add(j)
                elif var2.get() and not var1.get():
                    rules_to_remove.add(i)
                elif not var1.get() and not var2.get():
                    rules_to_remove.add(i)
                    rules_to_remove.add(j)

            if rules_to_remove:
                # удаляем с конца, чтобы не сбить индексы
                for rule_idx in sorted(rules_to_remove, reverse=True):
                    removed_rule = self.rules.pop(rule_idx)
                    self.add_log_entry(f"Удалено конфликтующее правило: {self.rule_to_string(removed_rule)}")

                self.save_rules()
                self.update_rules_list()
                messagebox.showinfo("Готово", f"Удалено правил: {len(rules_to_remove)}")

            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="✅ Применить выбранное", command=resolve_conflicts).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Отмена", command=dialog.destroy).pack(side='left', padx=5)

    def add_rule(self):
        """Добавление нового правила"""
        # формируем правило
        new_rule = {
            'device': self.device_var.get(),
            'action': self.action_var.get()
        }

        # добавляем таймер, если включен
        if self.timer_enabled.get():
            try:
                timer_minutes = int(self.timer_value.get())
                if timer_minutes > 0:
                    new_rule['timer'] = timer_minutes
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное значение таймера")
                return

        # добавляем только отмеченные условия
        if self.use_temp.get() and self.temp_value.get().strip():
            new_rule['temperature'] = f"{self.temp_operator.get()}{self.temp_value.get()}"

        if self.use_hum.get() and self.hum_value.get().strip():
            new_rule['humidity'] = f"{self.hum_operator.get()}{self.hum_value.get()}"

        if self.use_light.get() and self.light_value.get().strip():
            new_rule['light'] = f"{self.light_operator.get()}{self.light_value.get()}"

        if self.use_time.get():
            new_rule['time_of_day'] = self.time_var.get()

        if self.use_motion.get():
            new_rule['motion'] = self.motion_var.get() == "есть"

        # проверяем на полные дубликаты
        for existing_rule in self.rules:
            if self.rules_equal(new_rule, existing_rule):
                messagebox.showinfo("Дубликат", "Такое правило уже существует!")
                return

        # проверяем на конфликты с уже существующими правилами
        conflicting = [r for r in self.rules if rules_conflict(new_rule, r)]
        if conflicting:
            rules_text = "\n".join(self.rule_to_string(r) for r in conflicting)
            response = messagebox.askyesno(
                "Конфликт правил",
                f"Новое правило может сработать одновременно с правилами, "
                f"дающими противоположное действие:\n{rules_text}\n\n"
                "Заменить их новым правилом?")
            if not response:
                return
            for r in conflicting:
                self.rules.remove(r)
                self.add_log_entry(f"Заменено правило: {self.rule_to_string(r)}")

        # добавляем правило
        self.rules.append(new_rule)
        self.save_rules()
        self.update_rules_list()
        self.add_log_entry(f"Добавлено правило: {self.rule_to_string(new_rule)}")

        # очищаем поля
        self.use_temp.set(False)
        self.use_hum.set(False)
        self.use_light.set(False)
        self.use_time.set(False)
        self.use_motion.set(False)
        self.timer_enabled.set(False)
        self.toggle_condition_widgets('temp', False)
        self.toggle_condition_widgets('hum', False)
        self.toggle_condition_widgets('light', False)
        self.time_combo.config(state='disabled')
        self.motion_combo.config(state='disabled')
        self.timer_entry.config(state='disabled')

    def rules_equal(self, rule1, rule2):
        """Проверка на полное совпадение правил"""
        if rule1['device'] != rule2['device'] or rule1['action'] != rule2['action']:
            return False

        for key in ['temperature', 'humidity', 'light', 'time_of_day', 'motion', 'timer']:
            if rule1.get(key) != rule2.get(key):
                return False

        return True

    def rule_to_string(self, rule):
        """Преобразование правила в строку для отображения"""
        conditions = []
        if 'temperature' in rule:
            conditions.append(f"температура {rule['temperature']}°C")
        if 'humidity' in rule:
            conditions.append(f"влажность {rule['humidity']}%")
        if 'light' in rule:
            conditions.append(f"освещённость {rule['light']}")
        if 'time_of_day' in rule:
            conditions.append(f"время {rule['time_of_day']}")
        if 'motion' in rule:
            conditions.append("движение")

        condition_str = ", ".join(conditions) if conditions else "всегда"
        timer_str = f" (таймер: {rule['timer']} мин)" if 'timer' in rule else ""

        return f"{rule['device']} ({condition_str}) → {rule['action']}{timer_str}"

    def delete_selected_rule(self):
        """Удаление выбранного правила"""
        selected = self.rules_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите правило для удаления")
            return

        item = self.rules_tree.item(selected[0])
        rule_id = int(item['values'][0]) - 1

        if 0 <= rule_id < len(self.rules):
            removed_rule = self.rules.pop(rule_id)
            self.save_rules()
            self.update_rules_list()
            self.add_log_entry(f"Удалено правило: {self.rule_to_string(removed_rule)}")

    def check_rules(self):
        """Проверка всех правил"""
        actions = []

        for rule in self.rules:
            conditions_met = rule_matches(rule, self.sensors, self.time_of_day)

            if conditions_met:
                action = f"{rule['action']} {rule['device']}"
                actions.append(action)

                # обновляем активные действия
                self.active_actions[rule['device']] = rule['action']

                self.add_log_entry(f"🟢 Выполнено: {action}")

                # если есть таймер, запускаем его
                if 'timer' in rule and rule['timer'] > 0:
                    self.start_timer(rule)

        return actions

    def start_timer(self, rule):
        """Запуск таймера для правила"""
        with self.timer_lock:
            # проверяем нет ли уже активного таймера для этого устройства
            for timer in self.active_timers:
                if timer['device'] == rule['device']:
                    # обновляем существующий таймер
                    timer['end_time'] = datetime.now() + timedelta(minutes=rule['timer'])
                    timer['action'] = rule['action']
                    timer['duration'] = rule['timer']
                    self.add_log_entry(f"⏱️ Обновлён таймер: {rule['device']} будет "
                                       f"{'включен' if rule['action'] == 'включить' else 'выключен'} "
                                       f"ещё {rule['timer']} минут")
                    self.root.after(0, self.update_timers_display)
                    return

            # создаём новый таймер
            timer = {
                'device': rule['device'],
                'action': rule['action'],
                'end_time': datetime.now() + timedelta(minutes=rule['timer']),
                'duration': rule['timer']
            }
            self.active_timers.append(timer)
            self.add_log_entry(f"⏱️ Запущен таймер: {rule['device']} {rule['action']} на {rule['timer']} минут")
            self.root.after(0, self.update_timers_display)

    def start_timer_checker(self):
        """Запуск проверки истекших таймеров"""
        self.timer_thread = threading.Thread(target=self.timer_checker_loop, daemon=True)
        self.timer_thread.start()

    def timer_checker_loop(self):
        """Цикл проверки таймеров"""
        while True:
            time.sleep(1)  # Проверяем каждую секунду для точности
            self.check_expired_timers()
            # Обновляем отображение таймеров
            self.root.after(0, self.update_timers_display)

    def check_expired_timers(self):
        """Проверка истекших таймеров"""
        with self.timer_lock:
            current_time = datetime.now()
            expired_timers = []

            for timer in self.active_timers:
                if current_time >= timer['end_time']:
                    expired_timers.append(timer)

            for timer in expired_timers:
                self.active_timers.remove(timer)
                # Выполняем обратное действие
                reverse_action = "выключить" if timer['action'] == "включить" else "включить"

                # Обновляем статус устройства
                self.active_actions[timer['device']] = reverse_action

                self.add_log_entry(f"⏰ Таймер истёк: {timer['device']} {reverse_action}")

    def update_timers_display(self):
        """Обновление отображения таймеров"""
        if not hasattr(self, 'timers_text'):
            return

        self.timers_text.delete('1.0', 'end')

        with self.timer_lock:
            if not self.active_timers:
                self.timers_text.insert('end', "Нет активных таймеров\n")
            else:
                current_time = datetime.now()
                for timer in self.active_timers:
                    remaining = timer['end_time'] - current_time
                    total_seconds = int(remaining.total_seconds())

                    if total_seconds > 0:
                        minutes = total_seconds // 60
                        seconds = total_seconds % 60

                        # создаём визуальный индикатор прогресса
                        total_duration = timer['duration'] * 60
                        progress = min(100, max(0, int((total_duration - total_seconds) / total_duration * 100)))

                        progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)

                        timer_str = (f"Устройство: {timer['device']}\n"
                                     f"Действие: {timer['action']}\n"
                                     f"Осталось: {minutes:02d}:{seconds:02d}\n"
                                     f"Прогресс: [{progress_bar}] {progress}%\n"
                                     f"{'=' * 40}\n")
                        self.timers_text.insert('end', timer_str)

    def start_simulation(self):
        """Запуск симуляции датчиков"""
        self.simulation_active = True
        self.simulation_thread = threading.Thread(target=self.simulation_loop, daemon=True)
        self.simulation_thread.start()

    def simulation_loop(self):
        """Цикл симуляции"""
        while self.simulation_active:
            # Обновляем показания датчиков
            self.sensors['temperature'] += random.uniform(-0.5, 0.5)
            self.sensors['temperature'] = round(max(15, min(35, self.sensors['temperature'])), 1)

            self.sensors['humidity'] += random.uniform(-3, 3)
            self.sensors['humidity'] = round(max(20, min(90, self.sensors['humidity'])), 1)

            self.sensors['light'] += random.randint(-10, 10)
            self.sensors['light'] = max(0, min(100, self.sensors['light']))

            if random.random() < 0.2:
                self.sensors['motion'] = random.choice([True, False])

            self.time_of_day = self.get_time_of_day()

            # проверяем правила
            self.check_rules()

            # обновляем отображение
            self.root.after(0, self.update_sensor_display)

            time.sleep(3)

    def toggle_simulation(self):
        """Включение/выключение симуляции"""
        if self.simulation_active:
            self.simulation_active = False
            self.sim_button.config(text="▶️ Запустить симуляцию")
            self.add_log_entry("⏸️ Симуляция остановлена")
        else:
            self.simulation_active = True
            self.sim_button.config(text="⏸️ Остановить симуляцию")
            self.start_simulation()
            self.add_log_entry("▶️ Симуляция запущена")

    def update_sensor_display(self):
        """Обновление отображения датчиков"""
        self.temp_label.config(text=f"🌡️ Температура: {self.sensors['temperature']} °C")
        self.hum_label.config(text=f"💧 Влажность: {self.sensors['humidity']} %")
        self.light_label.config(text=f"💡 Освещённость: {self.sensors['light']}")
        self.motion_label.config(text=f"🏃 Движение: {'Да' if self.sensors['motion'] else 'Нет'}")
        self.time_label.config(text=f"🕐 Время суток: {self.time_of_day}")

    def apply_manual_values(self):
        """Применение ручных значений всех датчиков"""
        # Округляем значения до десятых
        self.sensors['temperature'] = round(self.manual_temp.get(), 1)
        self.sensors['humidity'] = round(self.manual_hum.get(), 1)
        self.sensors['light'] = round(self.manual_light.get())
        self.sensors['motion'] = self.manual_motion.get()
        self.time_of_day = self.manual_time.get()

        self.add_log_entry(f"🔧 Ручная установка: t={self.sensors['temperature']}°C, "
                           f"h={self.sensors['humidity']}%, l={self.sensors['light']}, "
                           f"m={'да' if self.sensors['motion'] else 'нет'}, "
                           f"время={self.time_of_day}")

        self.update_sensor_display()
        self.check_rules()

    def add_log_entry(self, message):
        """Добавление записи в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log.append(log_entry)

        if len(self.log) > 1000:
            self.log = self.log[-1000:]

        if hasattr(self, 'log_text'):
            self.log_text.insert('end', log_entry + '\n')
            self.log_text.see('end')

    def clear_log(self):
        """Очистка лога"""
        self.log = []
        self.log_text.delete('1.0', 'end')
        self.add_log_entry("🗑️ Лог очищен")

    def save_log(self):
        """Сохранение лога в файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"smart_home_log_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            for entry in self.log:
                f.write(entry + '\n')

        messagebox.showinfo("Сохранено", f"Лог сохранён в файл: {filename}")

    def update_rules_list(self):
        """Обновление списка правил в treeview"""
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)

        for i, rule in enumerate(self.rules):
            conditions = []
            if 'temperature' in rule:
                conditions.append(f"Темп: {rule['temperature']}°C")
            if 'humidity' in rule:
                conditions.append(f"Влаж: {rule['humidity']}%")
            if 'light' in rule:
                conditions.append(f"Свет: {rule['light']}")
            if 'time_of_day' in rule:
                conditions.append(f"Время: {rule['time_of_day']}")
            if 'motion' in rule:
                conditions.append("Движение")

            condition_str = ", ".join(conditions) if conditions else "Всегда"
            timer_str = f"{rule['timer']} мин" if 'timer' in rule else "Нет"

            self.rules_tree.insert('', 'end',
                                   values=(i + 1, rule['device'], condition_str, rule['action'], timer_str))

    def save_rules(self):
        """Сохранение правил в файл"""
        with open('smart_home_rules.json', 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)

    def load_rules(self):
        """Загрузка правил из файла"""
        try:
            with open('smart_home_rules.json', 'r', encoding='utf-8') as f:
                self.rules = json.load(f)
            self.add_log_entry("📂 Правила загружены из файла")
            self.update_rules_list()
        except FileNotFoundError:
            self.rules = []
            self.save_rules()
            self.add_log_entry("📝 Файл правил не найден, создан новый")


def main():
    root = tk.Tk()
    app = SmartHomeController(root)
    root.mainloop()


if __name__ == "__main__":
    main()