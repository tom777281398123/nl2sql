-- 创建 dw 和 meta 两个数据库
CREATE DATABASE IF NOT EXISTS dw CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE DATABASE IF NOT EXISTS meta CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- 授予用户权限
GRANT ALL PRIVILEGES ON dw.* TO 'storekeeper'@'%';
GRANT ALL PRIVILEGES ON meta.* TO 'storekeeper'@'%';
FLUSH PRIVILEGES;
