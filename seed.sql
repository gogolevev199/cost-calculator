-- =========================================================
-- USERS
-- =========================================================

INSERT INTO users (login, password_hash, full_name, role, is_active)
VALUES (
    'admin',
    'admin123',
    'Administrator',
    'admin',
    TRUE
)
ON CONFLICT (login) DO NOTHING;

-- =========================================================
-- TRANSPORT TYPES
-- =========================================================

INSERT INTO transport_types (name, code, notes, is_active)
VALUES
    ('Авто', 'auto', 'Автомобильный транспорт', TRUE),
    ('Ж/д', 'rail', 'Железнодорожный транспорт', TRUE),
    ('Сборный груз', 'groupage', 'Сборный груз', TRUE),
    ('Самовывоз', 'pickup', 'Самовывоз клиентом', TRUE)
ON CONFLICT (code) DO NOTHING;

-- =========================================================
-- TRANSPORT SCHEMES
-- =========================================================

INSERT INTO transport_schemes (transport_type_id, name, capacity_tons, is_standard, notes, is_active)
SELECT id, 'Авто 20 т', 20, TRUE, 'Стандартная автомобильная перевозка 20 тонн', TRUE
FROM transport_types
WHERE code = 'auto'
ON CONFLICT DO NOTHING;

INSERT INTO transport_schemes (transport_type_id, name, capacity_tons, is_standard, notes, is_active)
SELECT id, 'Ж/д полувагон 67 т', 67, TRUE, 'Стандартный полувагон 67 тонн', TRUE
FROM transport_types
WHERE code = 'rail'
ON CONFLICT DO NOTHING;

INSERT INTO transport_schemes (transport_type_id, name, capacity_tons, is_standard, notes, is_active)
SELECT id, 'Ж/д хоппер 67 т', 67, TRUE, 'Стандартный хоппер 67 тонн', TRUE
FROM transport_types
WHERE code = 'rail'
ON CONFLICT DO NOTHING;

INSERT INTO transport_schemes (transport_type_id, name, capacity_tons, is_standard, notes, is_active)
SELECT id, 'Сборный груз', NULL, TRUE, 'Сборный груз без фиксированной грузоподъемности', TRUE
FROM transport_types
WHERE code = 'groupage'
ON CONFLICT DO NOTHING;

INSERT INTO transport_schemes (transport_type_id, name, capacity_tons, is_standard, notes, is_active)
SELECT id, 'Самовывоз', NULL, TRUE, 'Клиент забирает продукцию самостоятельно', TRUE
FROM transport_types
WHERE code = 'pickup'
ON CONFLICT DO NOTHING;

-- =========================================================
-- EXTRA TRANSPORT COST TYPES
-- =========================================================

INSERT INTO transport_extra_cost_types (name, code, notes, is_active)
VALUES
    ('Доп. упаковка', 'extra_packaging', 'Дополнительная упаковка', TRUE),
    ('Погрузка', 'loading', 'Погрузка продукции', TRUE),
    ('Разгрузка', 'unloading', 'Разгрузка продукции', TRUE),
    ('Перевалка', 'reloading', 'Перевалка груза', TRUE),
    ('Хранение', 'storage', 'Временное хранение груза', TRUE),
    ('Страховка', 'insurance', 'Страхование перевозки', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO operations (name, code, operation_group, unit, default_loss_coefficient, is_active)
VALUES
    ('Смешивание', 'mixing', 'common', 'ton', 1.000000, TRUE),
    ('Фасовка', 'packing', 'common', 'ton', 1.000000, TRUE),
    ('Дробление', 'crushing', 'process', 'ton', 1.010000, TRUE),
    ('Сушка', 'drying', 'process', 'ton', 1.030000, TRUE),
    ('Помол', 'milling', 'process', 'ton', 1.020000, TRUE)
ON CONFLICT (code) DO NOTHING;