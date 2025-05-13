import tkinter as tk
import math
import time
import random
from pynput import mouse
from PIL import Image, ImageDraw, ImageTk

# Общие параметры
window_width = 1200
window_height = 600
eye_radius = 120
pupil_radius = 40 # Базовый радиус зрачка
iris_radius = 60
max_pupil_offset = 72  # 60% от радиуса белка

# Позиции центров глаз (относительно окна Tkinter)
left_eye_center_x_win = 300
left_eye_center_y_win = 300
right_eye_center_x_win = 900
right_eye_center_y_win = 300

# Параметры моргания
blink_duration = 300  # мс
blink_interval_min = 2  # секунды
blink_interval_max = 5  # секунды
blink_steps = 30  # Увеличим количество шагов для более плавной анимации

# Параметры плавного движения зрачков
pupil_move_speed = 0.1 # Коэффициент скорости движения (от 0 до 1)

# Коэффициент параллакса (от 0 до 1)
parallax_coefficient = 0.3

# Коэффициент перспективного сжатия белка (0 - нет, >0 - есть)
perspective_squash_factor = 0.15

# Размер изображения одного глаза для Pillow (увеличено для обводки и сглаживания)
eye_img_size = eye_radius * 2 + 45

# Минимальная высота для отрисовки ограниченного эллипса
min_ellipse_height = 1 # Пиксели

# Интервал обновления для желаемой частоты кадров (в мс) 
update_interval_ms = 6 # ~166 Гц. НАСТРОЙТЕ ПОД СЕБЯ!!!!

# Параметры дрейфа
drift_amount = 0.5  # Максимальное случайное смещение за один шаг дрейфа
drift_interval_ms = 50 # Интервал между шагами дрейфа в мс

# --- Параметры изменения размера зрачка --- 
pupil_size_speed_factor = 0.05 # Скорость анимации изменения размера

# Состояния, зависящие от курсора
max_pupil_expansion_speed = 10 # Добавка к радиусу при быстрой скорости
cursor_speed_threshold = 10 # Порог скорости курсора
pupil_expansion_inactivity = 3 # Добавка к радиусу при бездействии
long_inactivity_time_threshold = 1.0 # Порог времени бездействия (секунды)

# Состояния, зависящие от расстояния
near_distance_factor = 0.25 # Порог для NEAR (доля от диагонали экрана)
far_distance_factor = 0.35 # Порог для FAR (доля от диагонали экрана)
distance_hysteresis_factor = 0.03 # Зона гистерезиса (доля от диагонали)
pupil_contraction_near = 10 # Насколько сужается в состоянии NEAR
pupil_expansion_far = 5 # Насколько расширяется в состоянии FAR
# Целевой радиус для MID рассчитывается как pupil_radius - (pupil_contraction_near / 2)

# Глобальное состояние расстояния для гистерезиса
current_distance_state = "MID"

def calculate_global_target_pupil_radius(mouse_x_global, mouse_y_global, left_eye, right_eye):
    """Рассчитывает целевой радиус зрачка на основе системы состояний с гистерезисом и относительными расстояниями."""
    global last_mouse_x, last_mouse_y, last_mouse_time, last_move_time, current_distance_state

    # --- Расчет параметров курсора (скорость, время бездействия) --- 
    current_time = time.time()
    mouse_speed = 0
    distance_moved = 0
    time_diff = 0

    if last_mouse_time is not None:
        time_diff = current_time - last_mouse_time
        if time_diff > 0:
            distance_moved = math.hypot(mouse_x_global - last_mouse_x, mouse_y_global - last_mouse_y)
            mouse_speed = distance_moved / time_diff

    if distance_moved > 1: # Обновляем время последнего движения
        last_move_time = current_time
    time_since_last_move = current_time - last_move_time

    # --- Расчет расстояния до ближайшего глаза --- 
    window_x = root.winfo_x()
    window_y = root.winfo_y()
    canvas_x = canvas.winfo_x()
    canvas_y = canvas.winfo_y()
    left_eye_center_x_global = window_x + canvas_x + left_eye.center_x_win
    left_eye_center_y_global = window_y + canvas_y + left_eye.center_y_win
    right_eye_center_x_global = window_x + canvas_x + right_eye.center_x_win
    right_eye_center_y_global = window_y + canvas_y + right_eye.center_y_win
    distance_to_left_eye = math.hypot(mouse_x_global - left_eye_center_x_global, mouse_y_global - left_eye_center_y_global)
    distance_to_right_eye = math.hypot(mouse_x_global - right_eye_center_x_global, mouse_y_global - right_eye_center_y_global)
    distance_to_closest_eye = min(distance_to_left_eye, distance_to_right_eye)

    # --- Расчет динамических порогов расстояния с гистерезисом --- 
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    screen_diagonal = math.sqrt(screen_width**2 + screen_height**2)
    hysteresis_margin = screen_diagonal * distance_hysteresis_factor
    near_enter_threshold = screen_diagonal * near_distance_factor
    near_leave_threshold = near_enter_threshold + hysteresis_margin
    far_enter_threshold = screen_diagonal * far_distance_factor
    far_leave_threshold = far_enter_threshold - hysteresis_margin

    # --- Определение состояния расстояния (NEAR, MID, FAR) с гистерезисом ---
    new_distance_state = current_distance_state
    if current_distance_state == "NEAR":
        if distance_to_closest_eye > near_leave_threshold:
            new_distance_state = "MID"
    elif current_distance_state == "MID":
        if distance_to_closest_eye < near_enter_threshold:
            new_distance_state = "NEAR"
        elif distance_to_closest_eye > far_enter_threshold:
            new_distance_state = "FAR"
    elif current_distance_state == "FAR":
        if distance_to_closest_eye < far_leave_threshold:
            new_distance_state = "MID"
    current_distance_state = new_distance_state # Обновляем глобальное состояние

    # --- Определение итогового состояния (с приоритетами) и целевого радиуса ---
    target_r = pupil_radius # Базовый радиус по умолчанию
    final_state = current_distance_state # Состояние расстояния

    # Приоритет 1: NEAR
    if current_distance_state == "NEAR":
        target_r = pupil_radius - pupil_contraction_near
        final_state = "NEAR"
    # Приоритет 2: FAST_MOVE (если не NEAR)
    elif mouse_speed > cursor_speed_threshold:
        target_r = pupil_radius + max_pupil_expansion_speed
        final_state = "FAST_MOVE"
    # Приоритет 3: IDLE (если не NEAR и не FAST_MOVE)
    elif time_since_last_move > long_inactivity_time_threshold:
        target_r = pupil_radius + pupil_expansion_inactivity
        final_state = "IDLE"
    # Приоритет 4: Состояния MID или FAR (если не приоритетные)
    else:
        if current_distance_state == "MID":
            target_r = pupil_radius - (pupil_contraction_near / 2)
            final_state = "MID"
        elif current_distance_state == "FAR":
            target_r = pupil_radius + pupil_expansion_far
            final_state = "FAR"

    # --- Ограничение итогового радиуса допустимыми пределами ---
    min_allowed_r = pupil_radius - pupil_contraction_near
    max_allowed_r = pupil_radius + max_pupil_expansion_speed
    target_r = max(min_allowed_r, min(target_r, max_allowed_r))

    # --- Обновление данных для следующего вызова ---
    last_mouse_x = mouse_x_global
    last_mouse_y = mouse_y_global
    last_mouse_time = current_time

    return target_r

class Eye:
    def __init__(self, canvas, center_x, center_y):
        self.canvas = canvas
        self.center_x_win = center_x
        self.center_y_win = center_y

        # Создаем изображение Pillow для этого глаза
        self.image = Image.new("RGBA", (eye_img_size, eye_img_size), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.image)

        # Создаем объект PhotoImage для Tkinter
        self.photo_image = ImageTk.PhotoImage(self.image)

        # Отображаем изображение на холсте Tkinter
        self.image_on_canvas = self.canvas.create_image(
            center_x, center_y,
            image=self.photo_image,
            anchor=tk.CENTER
        )

        # Текущие смещения зрачка/радужки
        self.current_pupil_offset_x = 0
        self.current_pupil_offset_y = 0
        self.target_pupil_offset_x = 0
        self.target_pupil_offset_y = 0

        # Смещение дрейфа
        self.drift_offset_x = 0
        self.drift_offset_y = 0

        self.is_blinking = False

        # Текущий и целевой радиус зрачка
        self.current_pupil_radius = pupil_radius
        self.target_pupil_radius = pupil_radius

        # Рисуем начальное состояние глаза
        self.draw_eye()


    def draw_eye(self, blink_offset=0):
        # Очищаем изображение
        self.draw.rectangle((0, 0, eye_img_size, eye_img_size), fill=(0, 0, 0, 0))

        # Координаты центра глаза на изображении Pillow
        img_center_x = eye_img_size // 2
        img_center_y = eye_img_size // 2

        # --- Расчет перспективного искажения и смещения --- 
        total_offset_x = self.current_pupil_offset_x + self.drift_offset_x
        total_offset_y = self.current_pupil_offset_y + self.drift_offset_y
        small_value = 1e-6
        norm_offset_x = abs(total_offset_x) / (max_pupil_offset + small_value)
        norm_offset_y = abs(total_offset_y) / (max_pupil_offset + small_value)
        squash_x = 1.0 - norm_offset_y * perspective_squash_factor
        squash_y = 1.0 - norm_offset_x * perspective_squash_factor
        effective_radius_x = eye_radius * squash_x
        effective_radius_y = eye_radius * squash_y

        white_offset_x = total_offset_x * parallax_coefficient
        white_offset_y = total_offset_y * parallax_coefficient

        # --- Расчет видимых границ белка (с учетом моргания и искажения) ---
        sclera_center_y = img_center_y + white_offset_y
        half_visible_sclera_height = max(0, effective_radius_y - blink_offset)
        visible_top = sclera_center_y - half_visible_sclera_height
        visible_bottom = sclera_center_y + half_visible_sclera_height

        # --- Рисуем белок (если его высота > 0) ---
        if visible_bottom > visible_top: # Избегаем ValueError
             white_bbox = (
                img_center_x - effective_radius_x + white_offset_x,
                visible_top,
                img_center_x + effective_radius_x + white_offset_x,
                visible_bottom
            )
             self.draw.ellipse(white_bbox, fill="white", outline="black", width=2)

        # --- Рисуем радужку (с искажением и вертикальным клиппингом) ---
        iris_offset_x = total_offset_x
        iris_offset_y = total_offset_y
        effective_iris_radius_x = iris_radius * squash_x
        effective_iris_radius_y = iris_radius * squash_y

        iris_center_x = img_center_x + iris_offset_x
        iris_center_y = img_center_y + iris_offset_y
        iris_top = iris_center_y - effective_iris_radius_y
        iris_bottom = iris_center_y + effective_iris_radius_y

        limited_iris_top = max(iris_top, visible_top)
        limited_iris_bottom = min(iris_bottom, visible_bottom)

        if limited_iris_bottom - limited_iris_top >= min_ellipse_height:
             iris_bbox = (
                iris_center_x - effective_iris_radius_x,
                limited_iris_top,
                iris_center_x + effective_iris_radius_x,
                limited_iris_bottom
            )
             if iris_bbox[3] >= iris_bbox[1] and iris_bbox[2] >= iris_bbox[0]: # Доп. проверка
                 self.draw.ellipse(iris_bbox, fill="#4A90D9")

        # --- Рисуем зрачок (с искажением и вертикальным клиппингом) ---
        pupil_offset_x = total_offset_x
        pupil_offset_y = total_offset_y
        current_pupil_r = self.current_pupil_radius
        effective_pupil_radius_x = current_pupil_r * squash_x
        effective_pupil_radius_y = current_pupil_r * squash_y

        pupil_center_x = img_center_x + pupil_offset_x
        pupil_center_y = img_center_y + pupil_offset_y
        pupil_top = pupil_center_y - effective_pupil_radius_y
        pupil_bottom = pupil_center_y + effective_pupil_radius_y

        limited_pupil_top = max(pupil_top, visible_top)
        limited_pupil_bottom = min(pupil_bottom, visible_bottom)

        if limited_pupil_bottom - limited_pupil_top >= min_ellipse_height:
            pupil_bbox = (
                pupil_center_x - effective_pupil_radius_x,
                limited_pupil_top,
                pupil_center_x + effective_pupil_radius_x,
                limited_pupil_bottom
            )
            if pupil_bbox[3] >= pupil_bbox[1] and pupil_bbox[2] >= pupil_bbox[0]: # Доп. проверка
                 self.draw.ellipse(pupil_bbox, fill="black")

        # Обновляем PhotoImage и изображение на холсте Tkinter
        self.photo_image = ImageTk.PhotoImage(self.image)
        self.canvas.itemconfig(self.image_on_canvas, image=self.photo_image)


    def set_target_pupil_position(self, mouse_x_global, mouse_y_global):
        # Получаем координаты центра глаза в глобальной системе координат
        window_x = root.winfo_x()
        window_y = root.winfo_y()
        canvas_x = canvas.winfo_x()
        canvas_y = canvas.winfo_y()

        eye_center_x_global = window_x + canvas_x + self.center_x_win
        eye_center_y_global = window_y + canvas_y + self.center_y_win


        dx = mouse_x_global - eye_center_x_global
        dy = mouse_y_global - eye_center_y_global
        distance = math.hypot(dx, dy)

        if distance > max_pupil_offset:
            angle = math.atan2(dy, dx)
            self.target_pupil_offset_x = math.cos(angle) * max_pupil_offset
            self.target_pupil_offset_y = math.sin(angle) * max_pupil_offset
        else:
            self.target_pupil_offset_x = dx
            self.target_pupil_offset_y = dy

    def update_pupil_position(self):
        # Плавное движение к целевой позиции для зрачка/радужки
        self.current_pupil_offset_x += (self.target_pupil_offset_x + self.drift_offset_x - self.current_pupil_offset_x) * pupil_move_speed
        self.current_pupil_offset_y += (self.target_pupil_offset_y + self.drift_offset_y - self.current_pupil_offset_y) * pupil_move_speed

        # Плавное изменение размера зрачка
        self.current_pupil_radius += (self.target_pupil_radius - self.current_pupil_radius) * pupil_size_speed_factor

        # Перерисовываем глаз с новым положением и размером зрачка
        if not self.is_blinking:
            self.draw_eye()

    def apply_drift(self):
        # Генерируем небольшое случайное смещение для дрейфа
        self.drift_offset_x = random.uniform(-drift_amount, drift_amount)
        self.drift_offset_y = random.uniform(-drift_amount, drift_amount)
        # Перерисовываем глаз, чтобы учесть смещение дрейфа
        if not self.is_blinking:
             self.draw_eye()


    def blink(self):
        if self.is_blinking:
            return

        self.is_blinking = True
        self.start_blink_time = time.time()
        self.animate_blink()

    def animate_blink(self):
        elapsed_time = time.time() - self.start_blink_time
        progress = min(elapsed_time / (blink_duration / 1000), 1.0)

        # Рассчитываем смещение для моргания с более плавным началом/концом
        if progress < 0.5:  # Закрытие
            t = progress * 2
            blink_offset = eye_radius * (0.5 - 0.5 * math.cos(math.pi * t))
        else:  # Открытие
            t = (progress - 0.5) * 2
            blink_offset = eye_radius * (0.5 + 0.5 * math.cos(math.pi * t))


        # Перерисовываем глаз с учетом моргания
        self.draw_eye(blink_offset)


        if progress < 1.0:
            self.canvas.after(int(blink_duration / blink_steps), self.animate_blink)
        else:
            self.is_blinking = False
            self.draw_eye(0) # Возвращаем глаз в полностью открытое состояние с blink_offset = 0

    def on_mouse_move_global(self, x, y, target_pupil_radius):
        # Обновляем целевую позицию зрачков на основе глобальных координат курсора
        self.set_target_pupil_position(x, y) # Используем self для вызова метода класса Eye

        # Устанавливаем целевой размер зрачка, рассчитанный глобальной функцией
        self.target_pupil_radius = target_pupil_radius

def update_eyes_positions(left_eye, right_eye):
    # Обновляем позиции и размер зрачков плавно
    left_eye.update_pupil_position()
    right_eye.update_pupil_position()
    # Используем новый интервал обновления
    root.after(update_interval_ms, update_eyes_positions, left_eye, right_eye)

# Переменные для отслеживания скорости и длительности движения курсора
last_mouse_x = None
last_mouse_y = None
last_mouse_time = None
last_move_time = time.time() # Время последнего значительного движения курсора

def schedule_blink(left_eye, right_eye):
    delay = random.randint(blink_interval_min, blink_interval_max) * 1000
    left_eye.blink()
    right_eye.blink()
    root.after(delay, schedule_blink, left_eye, right_eye)

def start_drift_animation(left_eye, right_eye):
    # Применяем дрейф к обоим глазам периодически
    left_eye.apply_drift()
    right_eye.apply_drift()
    root.after(drift_interval_ms, start_drift_animation, left_eye, right_eye)


# Главное окно
root = tk.Tk()
root.title("Глаза-наблюдатели")
root.geometry(f"{window_width}x{window_height}")

# Холст
canvas = tk.Canvas(root, width=window_width, height=window_height, bg="#F0F0F0")
canvas.pack()

# Глаза
left_eye = Eye(canvas, left_eye_center_x_win, left_eye_center_y_win)
right_eye = Eye(canvas, right_eye_center_x_win, right_eye_center_y_win)

# Обновление позиций и размера зрачков
update_eyes_positions(left_eye, right_eye)

# Моргание
schedule_blink(left_eye, right_eye)

# Анимацая дрейфа
start_drift_animation(left_eye, right_eye)

# Глобальный слушатель мыши
listener = mouse.Listener(on_move=lambda x, y: (
    global_target_r := calculate_global_target_pupil_radius(x, y, left_eye, right_eye),
    left_eye.on_mouse_move_global(x, y, global_target_r),
    right_eye.on_mouse_move_global(x, y, global_target_r)
))
listener.start()

# Главный цикл tkinter
root.mainloop()