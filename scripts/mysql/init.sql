-- ============================================
-- 数据库初始化脚本
-- 包含数据仓库(dw)和元数据(meta)的表结构和数据
-- ============================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================
-- 第一部分: 数据仓库(dw) - 表结构
-- ============================================

-- ----------------------------
-- Table structure for dim_customer
-- ----------------------------
DROP TABLE IF EXISTS `dim_customer`;
CREATE TABLE `dim_customer`  (
  `customer_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `customer_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `gender` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `member_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  PRIMARY KEY (`customer_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dim_date
-- ----------------------------
DROP TABLE IF EXISTS `dim_date`;
CREATE TABLE `dim_date`  (
  `date_id` int NOT NULL,
  `year` int NULL DEFAULT NULL,
  `quarter` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `month` int NULL DEFAULT NULL,
  `day` int NULL DEFAULT NULL,
  PRIMARY KEY (`date_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dim_product
-- ----------------------------
DROP TABLE IF EXISTS `dim_product`;
CREATE TABLE `dim_product`  (
  `product_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `product_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `brand` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  PRIMARY KEY (`product_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for dim_region
-- ----------------------------
DROP TABLE IF EXISTS `dim_region`;
CREATE TABLE `dim_region`  (
  `region_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `province` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `region_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `country` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  PRIMARY KEY (`region_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for fact_order
-- ----------------------------
DROP TABLE IF EXISTS `fact_order`;
CREATE TABLE `fact_order`  (
  `order_id` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `customer_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `product_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `date_id` int NULL DEFAULT NULL,
  `region_id` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `order_quantity` int NULL DEFAULT NULL,
  `order_amount` float NULL DEFAULT NULL,
  PRIMARY KEY (`order_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ============================================
-- 第二部分: 元数据(meta) - 表结构
-- ============================================

-- ----------------------------
-- Table structure for column_info
-- ----------------------------
DROP TABLE IF EXISTS `column_info`;
CREATE TABLE `column_info`  (
  `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '列编号',
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '列名称',
  `type` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据类型',
  `role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '列类型(primary_key,foreign_key,measure,dimension)',
  `examples` json NULL COMMENT '数据示例',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '列描述',
  `alias` json NULL COMMENT '列别名',
  `table_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '所属表编号',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for column_metric
-- ----------------------------
DROP TABLE IF EXISTS `column_metric`;
CREATE TABLE `column_metric`  (
  `column_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '列编号',
  `metric_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指标编号',
  PRIMARY KEY (`column_id`, `metric_id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for metric_info
-- ----------------------------
DROP TABLE IF EXISTS `metric_info`;
CREATE TABLE `metric_info`  (
  `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '指标编码',
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '指标名称',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '指标描述',
  `relevant_columns` json NULL COMMENT '关联的列',
  `alias` json NULL COMMENT '指标别名',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for table_info
-- ----------------------------
DROP TABLE IF EXISTS `table_info`;
CREATE TABLE `table_info`  (
  `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '表编号',
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '表名称',
  `role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '表类型(fact/dim)',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '表描述',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ============================================
-- 第三部分: 数据仓库(dw) - 数据插入
-- ============================================

-- ----------------------------
-- Records of dim_customer
-- ----------------------------
INSERT INTO `dim_customer` VALUES ('C001', '李伟', '男', '黄金');
INSERT INTO `dim_customer` VALUES ('C002', '王芳', '女', '白银');
INSERT INTO `dim_customer` VALUES ('C003', '张敏', '女', '黄金');
INSERT INTO `dim_customer` VALUES ('C004', '刘洋', '男', '青铜');
INSERT INTO `dim_customer` VALUES ('C005', '陈静', '女', '铂金');
INSERT INTO `dim_customer` VALUES ('C006', '赵磊', '男', '白银');
INSERT INTO `dim_customer` VALUES ('C007', '黄秀英', '女', '青铜');
INSERT INTO `dim_customer` VALUES ('C008', '吴斌', '男', '黄金');
INSERT INTO `dim_customer` VALUES ('C009', '周燕', '女', '铂金');
INSERT INTO `dim_customer` VALUES ('C010', '徐浩', '男', '白银');
INSERT INTO `dim_customer` VALUES ('C011', '孙丽', '女', '黄金');
INSERT INTO `dim_customer` VALUES ('C012', '马强', '男', '青铜');
INSERT INTO `dim_customer` VALUES ('C013', '朱玲', '女', '白银');
INSERT INTO `dim_customer` VALUES ('C014', '胡杰', '男', '黄金');
INSERT INTO `dim_customer` VALUES ('C015', '高梅', '女', '铂金');
INSERT INTO `dim_customer` VALUES ('C016', '林峰', '男', '青铜');
INSERT INTO `dim_customer` VALUES ('C017', '何娜', '女', '白银');
INSERT INTO `dim_customer` VALUES ('C018', '郭涛', '男', '黄金');
INSERT INTO `dim_customer` VALUES ('C019', '邓慧', '女', '青铜');
INSERT INTO `dim_customer` VALUES ('C020', '曹瑞', '男', '铂金');

-- ----------------------------
-- Records of dim_date
-- ----------------------------
INSERT INTO `dim_date` VALUES (20250101, 2025, 'Q1', 1, 1);
INSERT INTO `dim_date` VALUES (20250102, 2025, 'Q1', 1, 2);
INSERT INTO `dim_date` VALUES (20250103, 2025, 'Q1', 1, 3);
INSERT INTO `dim_date` VALUES (20250104, 2025, 'Q1', 1, 4);
INSERT INTO `dim_date` VALUES (20250105, 2025, 'Q1', 1, 5);
INSERT INTO `dim_date` VALUES (20250106, 2025, 'Q1', 1, 6);
INSERT INTO `dim_date` VALUES (20250107, 2025, 'Q1', 1, 7);
INSERT INTO `dim_date` VALUES (20250108, 2025, 'Q1', 1, 8);
INSERT INTO `dim_date` VALUES (20250109, 2025, 'Q1', 1, 9);
INSERT INTO `dim_date` VALUES (20250110, 2025, 'Q1', 1, 10);
INSERT INTO `dim_date` VALUES (20250111, 2025, 'Q1', 1, 11);
INSERT INTO `dim_date` VALUES (20250112, 2025, 'Q1', 1, 12);
INSERT INTO `dim_date` VALUES (20250113, 2025, 'Q1', 1, 13);
INSERT INTO `dim_date` VALUES (20250114, 2025, 'Q1', 1, 14);
INSERT INTO `dim_date` VALUES (20250115, 2025, 'Q1', 1, 15);
INSERT INTO `dim_date` VALUES (20250116, 2025, 'Q1', 1, 16);
INSERT INTO `dim_date` VALUES (20250117, 2025, 'Q1', 1, 17);
INSERT INTO `dim_date` VALUES (20250118, 2025, 'Q1', 1, 18);
INSERT INTO `dim_date` VALUES (20250119, 2025, 'Q1', 1, 19);
INSERT INTO `dim_date` VALUES (20250120, 2025, 'Q1', 1, 20);
INSERT INTO `dim_date` VALUES (20250121, 2025, 'Q1', 1, 21);
INSERT INTO `dim_date` VALUES (20250122, 2025, 'Q1', 1, 22);
INSERT INTO `dim_date` VALUES (20250123, 2025, 'Q1', 1, 23);
INSERT INTO `dim_date` VALUES (20250124, 2025, 'Q1', 1, 24);
INSERT INTO `dim_date` VALUES (20250125, 2025, 'Q1', 1, 25);
INSERT INTO `dim_date` VALUES (20250126, 2025, 'Q1', 1, 26);
INSERT INTO `dim_date` VALUES (20250127, 2025, 'Q1', 1, 27);
INSERT INTO `dim_date` VALUES (20250128, 2025, 'Q1', 1, 28);
INSERT INTO `dim_date` VALUES (20250129, 2025, 'Q1', 1, 29);
INSERT INTO `dim_date` VALUES (20250130, 2025, 'Q1', 1, 30);
INSERT INTO `dim_date` VALUES (20250131, 2025, 'Q1', 1, 31);
INSERT INTO `dim_date` VALUES (20250201, 2025, 'Q1', 2, 1);
INSERT INTO `dim_date` VALUES (20250202, 2025, 'Q1', 2, 2);
INSERT INTO `dim_date` VALUES (20250203, 2025, 'Q1', 2, 3);
INSERT INTO `dim_date` VALUES (20250204, 2025, 'Q1', 2, 4);
INSERT INTO `dim_date` VALUES (20250205, 2025, 'Q1', 2, 5);
INSERT INTO `dim_date` VALUES (20250206, 2025, 'Q1', 2, 6);
INSERT INTO `dim_date` VALUES (20250207, 2025, 'Q1', 2, 7);
INSERT INTO `dim_date` VALUES (20250208, 2025, 'Q1', 2, 8);
INSERT INTO `dim_date` VALUES (20250209, 2025, 'Q1', 2, 9);
INSERT INTO `dim_date` VALUES (20250210, 2025, 'Q1', 2, 10);
INSERT INTO `dim_date` VALUES (20250211, 2025, 'Q1', 2, 11);
INSERT INTO `dim_date` VALUES (20250212, 2025, 'Q1', 2, 12);
INSERT INTO `dim_date` VALUES (20250213, 2025, 'Q1', 2, 13);
INSERT INTO `dim_date` VALUES (20250214, 2025, 'Q1', 2, 14);
INSERT INTO `dim_date` VALUES (20250215, 2025, 'Q1', 2, 15);
INSERT INTO `dim_date` VALUES (20250216, 2025, 'Q1', 2, 16);
INSERT INTO `dim_date` VALUES (20250217, 2025, 'Q1', 2, 17);
INSERT INTO `dim_date` VALUES (20250218, 2025, 'Q1', 2, 18);
INSERT INTO `dim_date` VALUES (20250219, 2025, 'Q1', 2, 19);
INSERT INTO `dim_date` VALUES (20250220, 2025, 'Q1', 2, 20);
INSERT INTO `dim_date` VALUES (20250221, 2025, 'Q1', 2, 21);
INSERT INTO `dim_date` VALUES (20250222, 2025, 'Q1', 2, 22);
INSERT INTO `dim_date` VALUES (20250223, 2025, 'Q1', 2, 23);
INSERT INTO `dim_date` VALUES (20250224, 2025, 'Q1', 2, 24);
INSERT INTO `dim_date` VALUES (20250225, 2025, 'Q1', 2, 25);
INSERT INTO `dim_date` VALUES (20250226, 2025, 'Q1', 2, 26);
INSERT INTO `dim_date` VALUES (20250227, 2025, 'Q1', 2, 27);
INSERT INTO `dim_date` VALUES (20250228, 2025, 'Q1', 2, 28);
INSERT INTO `dim_date` VALUES (20250301, 2025, 'Q1', 3, 1);
INSERT INTO `dim_date` VALUES (20250302, 2025, 'Q1', 3, 2);
INSERT INTO `dim_date` VALUES (20250303, 2025, 'Q1', 3, 3);
INSERT INTO `dim_date` VALUES (20250304, 2025, 'Q1', 3, 4);
INSERT INTO `dim_date` VALUES (20250305, 2025, 'Q1', 3, 5);
INSERT INTO `dim_date` VALUES (20250306, 2025, 'Q1', 3, 6);
INSERT INTO `dim_date` VALUES (20250307, 2025, 'Q1', 3, 7);
INSERT INTO `dim_date` VALUES (20250308, 2025, 'Q1', 3, 8);
INSERT INTO `dim_date` VALUES (20250309, 2025, 'Q1', 3, 9);
INSERT INTO `dim_date` VALUES (20250310, 2025, 'Q1', 3, 10);
INSERT INTO `dim_date` VALUES (20250311, 2025, 'Q1', 3, 11);
INSERT INTO `dim_date` VALUES (20250312, 2025, 'Q1', 3, 12);
INSERT INTO `dim_date` VALUES (20250313, 2025, 'Q1', 3, 13);
INSERT INTO `dim_date` VALUES (20250314, 2025, 'Q1', 3, 14);
INSERT INTO `dim_date` VALUES (20250315, 2025, 'Q1', 3, 15);
INSERT INTO `dim_date` VALUES (20250316, 2025, 'Q1', 3, 16);
INSERT INTO `dim_date` VALUES (20250317, 2025, 'Q1', 3, 17);
INSERT INTO `dim_date` VALUES (20250318, 2025, 'Q1', 3, 18);
INSERT INTO `dim_date` VALUES (20250319, 2025, 'Q1', 3, 19);
INSERT INTO `dim_date` VALUES (20250320, 2025, 'Q1', 3, 20);
INSERT INTO `dim_date` VALUES (20250321, 2025, 'Q1', 3, 21);
INSERT INTO `dim_date` VALUES (20250322, 2025, 'Q1', 3, 22);
INSERT INTO `dim_date` VALUES (20250323, 2025, 'Q1', 3, 23);
INSERT INTO `dim_date` VALUES (20250324, 2025, 'Q1', 3, 24);
INSERT INTO `dim_date` VALUES (20250325, 2025, 'Q1', 3, 25);
INSERT INTO `dim_date` VALUES (20250326, 2025, 'Q1', 3, 26);
INSERT INTO `dim_date` VALUES (20250327, 2025, 'Q1', 3, 27);
INSERT INTO `dim_date` VALUES (20250328, 2025, 'Q1', 3, 28);
INSERT INTO `dim_date` VALUES (20250329, 2025, 'Q1', 3, 29);
INSERT INTO `dim_date` VALUES (20250330, 2025, 'Q1', 3, 30);
INSERT INTO `dim_date` VALUES (20250331, 2025, 'Q1', 3, 31);

-- ----------------------------
-- Records of dim_product
-- ----------------------------
INSERT INTO `dim_product` VALUES ('P001', 'iPhone 15 Pro', '手机数码', '苹果');
INSERT INTO `dim_product` VALUES ('P002', 'Galaxy S24 Ultra', '手机数码', '三星');
INSERT INTO `dim_product` VALUES ('P003', 'Mate 60 Pro', '手机数码', '华为');
INSERT INTO `dim_product` VALUES ('P004', '戴森 V15 吸尘器', '家用电器', '戴森');
INSERT INTO `dim_product` VALUES ('P005', '美的空调 KFR-35GW', '家用电器', '美的');
INSERT INTO `dim_product` VALUES ('P006', '耐克 Air Max 270 运动鞋', '鞋靴', '耐克');
INSERT INTO `dim_product` VALUES ('P007', '阿迪达斯 Ultraboost 跑鞋', '鞋靴', '阿迪达斯');
INSERT INTO `dim_product` VALUES ('P008', '优衣库 Heattech 保暖夹克', '服饰', '优衣库');
INSERT INTO `dim_product` VALUES ('P009', '李维斯 501 牛仔裤', '服饰', '李维斯');
INSERT INTO `dim_product` VALUES ('P010', '雀巢金牌速溶咖啡', '食品饮料', '雀巢');
INSERT INTO `dim_product` VALUES ('P011', '蒙牛纯牛奶 250ml*12', '食品饮料', '蒙牛');
INSERT INTO `dim_product` VALUES ('P012', '乐事原味薯片 150g', '休闲零食', '乐事');
INSERT INTO `dim_product` VALUES ('P013', '奥利奥巧克力夹心饼干', '休闲零食', '奥利奥');
INSERT INTO `dim_product` VALUES ('P014', 'Kindle Paperwhite 电子书', '手机数码', '亚马逊');
INSERT INTO `dim_product` VALUES ('P015', 'Instant Pot 多功能电压力锅', '家用电器', 'Instant Pot');

-- ----------------------------
-- Records of dim_region
-- ----------------------------
INSERT INTO `dim_region` VALUES ('R001', '广东省', '华南', '中国');
INSERT INTO `dim_region` VALUES ('R002', '浙江省', '华东', '中国');
INSERT INTO `dim_region` VALUES ('R003', '四川省', '西南', '中国');
INSERT INTO `dim_region` VALUES ('R004', '北京市', '华北', '中国');
INSERT INTO `dim_region` VALUES ('R005', '上海市', '华东', '中国');
INSERT INTO `dim_region` VALUES ('R006', '湖北省', '华中', '中国');

-- ----------------------------
-- Records of fact_order
-- ----------------------------
INSERT INTO `fact_order` VALUES ('ORD20250101001', 'C001', 'P001', 20250101, 'R001', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250101002', 'C005', 'P003', 20250101, 'R005', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250102001', 'C003', 'P010', 20250102, 'R002', 5, 125);
INSERT INTO `fact_order` VALUES ('ORD20250102002', 'C008', 'P006', 20250102, 'R004', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250103001', 'C012', 'P011', 20250103, 'R003', 12, 60);
INSERT INTO `fact_order` VALUES ('ORD20250103002', 'C015', 'P014', 20250103, 'R005', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250104001', 'C002', 'P012', 20250104, 'R001', 8, 40);
INSERT INTO `fact_order` VALUES ('ORD20250105001', 'C007', 'P008', 20250105, 'R006', 2, 299);
INSERT INTO `fact_order` VALUES ('ORD20250105002', 'C010', 'P010', 20250105, 'R002', 8, 200);
INSERT INTO `fact_order` VALUES ('ORD20250106001', 'C010', 'P002', 20250106, 'R002', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250107001', 'C019', 'P013', 20250107, 'R003', 10, 35);
INSERT INTO `fact_order` VALUES ('ORD20250108001', 'C004', 'P005', 20250108, 'R001', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250108002', 'C016', 'P005', 20250108, 'R001', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250109001', 'C011', 'P009', 20250109, 'R004', 1, 599);
INSERT INTO `fact_order` VALUES ('ORD20250110001', 'C006', 'P007', 20250110, 'R005', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250110002', 'C003', 'P010', 20250110, 'R002', 5, 125);
INSERT INTO `fact_order` VALUES ('ORD20250111001', 'C013', 'P004', 20250111, 'R002', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250112001', 'C017', 'P015', 20250112, 'R006', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250113001', 'C020', 'P001', 20250113, 'R005', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250114001', 'C009', 'P010', 20250114, 'R004', 3, 75);
INSERT INTO `fact_order` VALUES ('ORD20250115001', 'C014', 'P003', 20250115, 'R001', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250116001', 'C001', 'P012', 20250116, 'R001', 6, 30);
INSERT INTO `fact_order` VALUES ('ORD20250117001', 'C005', 'P006', 20250117, 'R005', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250118001', 'C003', 'P011', 20250118, 'R002', 10, 50);
INSERT INTO `fact_order` VALUES ('ORD20250119001', 'C008', 'P014', 20250119, 'R004', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250120001', 'C012', 'P008', 20250120, 'R003', 1, 199);
INSERT INTO `fact_order` VALUES ('ORD20250120002', 'C014', 'P013', 20250120, 'R001', 25, 87.5);
INSERT INTO `fact_order` VALUES ('ORD20250121001', 'C015', 'P002', 20250121, 'R005', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250122001', 'C002', 'P013', 20250122, 'R001', 12, 42);
INSERT INTO `fact_order` VALUES ('ORD20250123001', 'C007', 'P005', 20250123, 'R006', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250124001', 'C010', 'P009', 20250124, 'R002', 2, 1198);
INSERT INTO `fact_order` VALUES ('ORD20250125001', 'C019', 'P007', 20250125, 'R003', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250125002', 'C018', 'P001', 20250125, 'R003', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250126001', 'C004', 'P004', 20250126, 'R001', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250127001', 'C011', 'P015', 20250127, 'R004', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250128001', 'C006', 'P001', 20250128, 'R005', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250129001', 'C013', 'P010', 20250129, 'R002', 4, 100);
INSERT INTO `fact_order` VALUES ('ORD20250130001', 'C017', 'P003', 20250130, 'R006', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250130002', 'C009', 'P010', 20250130, 'R004', 6, 150);
INSERT INTO `fact_order` VALUES ('ORD20250131001', 'C020', 'P012', 20250131, 'R005', 7, 35);
INSERT INTO `fact_order` VALUES ('ORD20250201001', 'C009', 'P011', 20250201, 'R004', 8, 40);
INSERT INTO `fact_order` VALUES ('ORD20250202001', 'C014', 'P006', 20250202, 'R001', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250203001', 'C001', 'P014', 20250203, 'R001', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250204001', 'C005', 'P008', 20250204, 'R005', 1, 199);
INSERT INTO `fact_order` VALUES ('ORD20250205001', 'C003', 'P002', 20250205, 'R002', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250205002', 'C008', 'P012', 20250205, 'R004', 12, 60);
INSERT INTO `fact_order` VALUES ('ORD20250206001', 'C008', 'P013', 20250206, 'R004', 9, 31.5);
INSERT INTO `fact_order` VALUES ('ORD20250207001', 'C012', 'P005', 20250207, 'R003', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250208001', 'C015', 'P009', 20250208, 'R005', 1, 599);
INSERT INTO `fact_order` VALUES ('ORD20250209001', 'C002', 'P007', 20250209, 'R001', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250210001', 'C007', 'P004', 20250210, 'R006', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250210002', 'C019', 'P011', 20250210, 'R003', 20, 100);
INSERT INTO `fact_order` VALUES ('ORD20250211001', 'C010', 'P015', 20250211, 'R002', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250212001', 'C019', 'P001', 20250212, 'R003', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250213001', 'C004', 'P010', 20250213, 'R001', 6, 150);
INSERT INTO `fact_order` VALUES ('ORD20250214001', 'C011', 'P003', 20250214, 'R004', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250215001', 'C006', 'P012', 20250215, 'R005', 10, 50);
INSERT INTO `fact_order` VALUES ('ORD20250215002', 'C016', 'P003', 20250215, 'R001', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250216001', 'C013', 'P011', 20250216, 'R002', 15, 75);
INSERT INTO `fact_order` VALUES ('ORD20250217001', 'C017', 'P006', 20250217, 'R006', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250218001', 'C020', 'P014', 20250218, 'R005', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250219001', 'C009', 'P008', 20250219, 'R004', 2, 398);
INSERT INTO `fact_order` VALUES ('ORD20250220001', 'C014', 'P002', 20250220, 'R001', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250220002', 'C006', 'P012', 20250220, 'R005', 18, 90);
INSERT INTO `fact_order` VALUES ('ORD20250221001', 'C001', 'P013', 20250221, 'R001', 11, 38.5);
INSERT INTO `fact_order` VALUES ('ORD20250222001', 'C005', 'P005', 20250222, 'R005', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250223001', 'C003', 'P009', 20250223, 'R002', 1, 599);
INSERT INTO `fact_order` VALUES ('ORD20250224001', 'C008', 'P007', 20250224, 'R004', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250225001', 'C012', 'P004', 20250225, 'R003', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250226001', 'C015', 'P015', 20250226, 'R005', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250227001', 'C002', 'P001', 20250227, 'R001', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250228001', 'C007', 'P010', 20250228, 'R006', 5, 125);
INSERT INTO `fact_order` VALUES ('ORD20250228002', 'C004', 'P012', 20250228, 'R001', 14, 70);
INSERT INTO `fact_order` VALUES ('ORD20250301001', 'C010', 'P003', 20250301, 'R002', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250301002', 'C017', 'P011', 20250301, 'R006', 30, 150);
INSERT INTO `fact_order` VALUES ('ORD20250302001', 'C019', 'P012', 20250302, 'R003', 9, 45);
INSERT INTO `fact_order` VALUES ('ORD20250303001', 'C004', 'P011', 20250303, 'R001', 10, 50);
INSERT INTO `fact_order` VALUES ('ORD20250304001', 'C011', 'P006', 20250304, 'R004', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250305001', 'C006', 'P014', 20250305, 'R005', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250305002', 'C007', 'P012', 20250305, 'R006', 20, 100);
INSERT INTO `fact_order` VALUES ('ORD20250306001', 'C013', 'P008', 20250306, 'R002', 1, 199);
INSERT INTO `fact_order` VALUES ('ORD20250307001', 'C017', 'P002', 20250307, 'R006', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250308001', 'C020', 'P013', 20250308, 'R005', 14, 49);
INSERT INTO `fact_order` VALUES ('ORD20250309001', 'C009', 'P005', 20250309, 'R004', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250310001', 'C014', 'P009', 20250310, 'R001', 1, 599);
INSERT INTO `fact_order` VALUES ('ORD20250310002', 'C013', 'P011', 20250310, 'R002', 20, 100);
INSERT INTO `fact_order` VALUES ('ORD20250311001', 'C001', 'P007', 20250311, 'R001', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250312001', 'C005', 'P004', 20250312, 'R005', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250312002', 'C012', 'P011', 20250312, 'R003', 24, 120);
INSERT INTO `fact_order` VALUES ('ORD20250313001', 'C003', 'P015', 20250313, 'R002', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250314001', 'C008', 'P001', 20250314, 'R004', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250315001', 'C012', 'P010', 20250315, 'R003', 7, 175);
INSERT INTO `fact_order` VALUES ('ORD20250315002', 'C020', 'P013', 20250315, 'R005', 22, 77);
INSERT INTO `fact_order` VALUES ('ORD20250316001', 'C015', 'P003', 20250316, 'R005', 1, 6999);
INSERT INTO `fact_order` VALUES ('ORD20250317001', 'C002', 'P012', 20250317, 'R001', 12, 60);
INSERT INTO `fact_order` VALUES ('ORD20250318001', 'C007', 'P011', 20250318, 'R006', 18, 90);
INSERT INTO `fact_order` VALUES ('ORD20250318002', 'C015', 'P013', 20250318, 'R005', 30, 105);
INSERT INTO `fact_order` VALUES ('ORD20250319001', 'C010', 'P006', 20250319, 'R002', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250320001', 'C019', 'P014', 20250320, 'R003', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250320002', 'C018', 'P014', 20250320, 'R003', 1, 1399);
INSERT INTO `fact_order` VALUES ('ORD20250321001', 'C004', 'P008', 20250321, 'R001', 3, 597);
INSERT INTO `fact_order` VALUES ('ORD20250322001', 'C011', 'P002', 20250322, 'R004', 1, 9499);
INSERT INTO `fact_order` VALUES ('ORD20250322002', 'C011', 'P011', 20250322, 'R004', 16, 80);
INSERT INTO `fact_order` VALUES ('ORD20250323001', 'C006', 'P013', 20250323, 'R005', 16, 56);
INSERT INTO `fact_order` VALUES ('ORD20250324001', 'C013', 'P005', 20250324, 'R002', 1, 3200);
INSERT INTO `fact_order` VALUES ('ORD20250325001', 'C017', 'P009', 20250325, 'R006', 2, 1198);
INSERT INTO `fact_order` VALUES ('ORD20250325002', 'C002', 'P010', 20250325, 'R001', 10, 250);
INSERT INTO `fact_order` VALUES ('ORD20250326001', 'C020', 'P007', 20250326, 'R005', 1, 1299);
INSERT INTO `fact_order` VALUES ('ORD20250327001', 'C009', 'P004', 20250327, 'R004', 1, 5499);
INSERT INTO `fact_order` VALUES ('ORD20250328001', 'C014', 'P015', 20250328, 'R001', 1, 899);
INSERT INTO `fact_order` VALUES ('ORD20250329001', 'C001', 'P001', 20250329, 'R001', 1, 8999);
INSERT INTO `fact_order` VALUES ('ORD20250329002', 'C005', 'P013', 20250329, 'R005', 18, 63);
INSERT INTO `fact_order` VALUES ('ORD20250330001', 'C005', 'P010', 20250330, 'R005', 4, 100);
INSERT INTO `fact_order` VALUES ('ORD20250330002', 'C008', 'P012', 20250330, 'R004', 15, 75);
INSERT INTO `fact_order` VALUES ('ORD20250331001', 'C003', 'P003', 20250331, 'R002', 1, 6999);

-- ============================================
-- 第四部分: 元数据(meta) - 数据插入
-- ============================================

-- ----------------------------
-- Records of column_info
-- ----------------------------
INSERT INTO `column_info` VALUES ('dim_customer.customer_id', 'customer_id', 'varchar(20)', 'primary_key', '["C001", "C002", "C003", "C004", "C005", "C006", "C007", "C008", "C009", "C010"]', '客户唯一标识。', '["客户ID", "用户ID"]', 'dim_customer');
INSERT INTO `column_info` VALUES ('dim_customer.customer_name', 'customer_name', 'varchar(50)', 'dimension', '["李伟", "王芳", "张敏", "刘洋", "陈静", "赵磊", "黄秀英", "吴斌", "周燕", "徐浩"]', '客户名称。', '["客户名称", "用户名称"]', 'dim_customer');
INSERT INTO `column_info` VALUES ('dim_customer.gender', 'gender', 'varchar(10)', 'dimension', '["男", "女"]', '客户性别。', '["性别"]', 'dim_customer');
INSERT INTO `column_info` VALUES ('dim_customer.member_level', 'member_level', 'varchar(20)', 'dimension', '["黄金", "白银", "青铜", "铂金"]', '客户会员等级。', '["会员等级", "用户等级"]', 'dim_customer');
INSERT INTO `column_info` VALUES ('dim_date.date_id', 'date_id', 'int', 'primary_key', '[20250101, 20250102, 20250103, 20250104, 20250105, 20250106, 20250107, 20250108, 20250109, 20250110]', '日期唯一标识，格式 yyyyMMdd。', '["日期ID", "日期"]', 'dim_date');
INSERT INTO `column_info` VALUES ('dim_date.day', 'day', 'int', 'dimension', '[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]', '日。', '["日", "天"]', 'dim_date');
INSERT INTO `column_info` VALUES ('dim_date.month', 'month', 'int', 'dimension', '[1, 2, 3]', '月份。', '["月", "月份"]', 'dim_date');
INSERT INTO `column_info` VALUES ('dim_date.quarter', 'quarter', 'varchar(2)', 'dimension', '["Q1"]', '季度。', '["季度"]', 'dim_date');
INSERT INTO `column_info` VALUES ('dim_date.year', 'year', 'int', 'dimension', '[2025]', '年份。', '["年", "年份"]', 'dim_date');
INSERT INTO `column_info` VALUES ('dim_product.brand', 'brand', 'varchar(50)', 'dimension', '["苹果", "三星", "华为", "戴森", "美的", "耐克", "阿迪达斯", "优衣库", "李维斯", "雀巢"]', '商品品牌名称。', '["品牌", "品牌名称"]', 'dim_product');
INSERT INTO `column_info` VALUES ('dim_product.category', 'category', 'varchar(50)', 'dimension', '["手机数码", "家用电器", "鞋靴", "服饰", "食品饮料", "休闲零食"]', '商品所属品类。', '["商品类别", "品类", "分类"]', 'dim_product');
INSERT INTO `column_info` VALUES ('dim_product.product_id', 'product_id', 'varchar(20)', 'primary_key', '["P001", "P002", "P003", "P004", "P005", "P006", "P007", "P008", "P009", "P010"]', '商品唯一标识。', '["商品ID", "产品ID"]', 'dim_product');
INSERT INTO `column_info` VALUES ('dim_product.product_name', 'product_name', 'varchar(200)', 'dimension', '["iPhone 15 Pro", "Galaxy S24 Ultra", "Mate 60 Pro", "戴森 V15 吸尘器", "美的空调 KFR-35GW", "耐克 Air Max 270 运动鞋", "阿迪达斯 Ultraboost 跑鞋", "优衣库 Heattech 保暖夹克", "李维斯 501 牛仔裤", "雀巢金牌速溶咖啡"]', '商品名称。', '["商品名称", "产品名称"]', 'dim_product');
INSERT INTO `column_info` VALUES ('dim_region.country', 'country', 'varchar(50)', 'dimension', '["中国"]', '地区所属国家名称。', '["国家", "国家名称"]', 'dim_region');
INSERT INTO `column_info` VALUES ('dim_region.province', 'province', 'varchar(50)', 'dimension', '["广东省", "浙江省", "四川省", "北京市", "上海市", "湖北省"]', '订单所属的省份名称。', '["省份", "省", "所在省份"]', 'dim_region');
INSERT INTO `column_info` VALUES ('dim_region.region_id', 'region_id', 'varchar(20)', 'primary_key', '["R001", "R002", "R003", "R004", "R005", "R006"]', '地区唯一标识。', '["地区ID", "区域ID"]', 'dim_region');
INSERT INTO `column_info` VALUES ('dim_region.region_name', 'region_name', 'varchar(50)', 'dimension', '["华南", "华东", "西南", "华北", "华中"]', '订单所属的大区名称，如华东、华南等。', '["地区", "区域", "大区"]', 'dim_region');
INSERT INTO `column_info` VALUES ('fact_order.customer_id', 'customer_id', 'varchar(20)', 'foreign_key', '["C001", "C005", "C003", "C008", "C012", "C015", "C002", "C007", "C010", "C019"]', '关联客户维度的外键。', '["客户ID", "用户ID"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.date_id', 'date_id', 'int', 'foreign_key', '[20250101, 20250102, 20250103, 20250104, 20250105, 20250106, 20250107, 20250108, 20250109, 20250110]', '关联时间维度的外键。', '["日期", "下单日期"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.order_amount', 'order_amount', 'float', 'measure', '[8999.0, 6999.0, 125.0, 899.0, 60.0, 1399.0, 40.0, 299.0, 200.0, 9499.0]', '订单金额。', '["销售额", "订单金额", "收入"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.order_id', 'order_id', 'varchar(30)', 'primary_key', '["ORD20250101001", "ORD20250101002", "ORD20250102001", "ORD20250102002", "ORD20250103001", "ORD20250103002", "ORD20250104001", "ORD20250105001", "ORD20250105002", "ORD20250106001"]', '订单唯一标识。', '["订单ID"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.order_quantity', 'order_quantity', 'int', 'measure', '[1, 5, 12, 8, 2, 10, 3, 6, 25, 4]', '订单中商品的购买数量。', '["销量", "购买数量", "件数"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.product_id', 'product_id', 'varchar(20)', 'foreign_key', '["P001", "P003", "P010", "P006", "P011", "P014", "P012", "P008", "P002", "P013"]', '关联商品维度的外键。', '["商品ID", "产品ID"]', 'fact_order');
INSERT INTO `column_info` VALUES ('fact_order.region_id', 'region_id', 'varchar(20)', 'foreign_key', '["R001", "R005", "R002", "R004", "R003", "R006"]', '关联地区维度的外键。', '["地区ID", "区域ID"]', 'fact_order');

-- ----------------------------
-- Records of column_metric
-- ----------------------------
INSERT INTO `column_metric` VALUES ('fact_order.order_amount', 'GMV');
INSERT INTO `column_metric` VALUES ('fact_order.order_quantity', 'AOV');

-- ----------------------------
-- Records of metric_info
-- ----------------------------
INSERT INTO `metric_info` VALUES ('AOV', 'AOV', '全称Average Order Value，表示所有订单的成交金额平均值。', '["fact_order.order_quantity"]', '["平均单价", "平均订单金额"]');
INSERT INTO `metric_info` VALUES ('GMV', 'GMV', '全称Gross Merchandise Value，表示所有订单的成交金额总和。', '["fact_order.order_amount"]', '["成交总额", "订单总额"]');

-- 订单类核心指标
INSERT INTO metric_info (id, name, description, relevant_columns, alias)
VALUES
-- 订单数量类
('ORDER_COUNT', '订单总数', '统计周期内的订单总数量，按order_id去重计数。', '["fact_order.order_id"]', '["订单数", "下单量"]'),
('ORDER_COUNT_BY_REGION', '各区域订单数', '按地区维度（region_id/region_name）统计的订单数量。', '["fact_order.order_id", "dim_region.region_id", "dim_region.region_name"]', '["区域订单量", "各地区下单数"]'),
-- 销量类
('SALES_QUANTITY', '商品销售总量', '统计周期内所有订单的商品购买数量总和。', '["fact_order.order_quantity"]', '["总销量", "销售件数"]'),
('SALES_QUANTITY_BY_CATEGORY', '品类销量', '按商品品类（category）统计的商品销售数量。', '["fact_order.order_quantity", "dim_product.category"]', '["品类销售件数", "分类销量"]'),
-- 客单价/消费能力类
('AVG_ORDER_QUANTITY', '平均订单商品数', '订单商品购买数量的平均值（总销量/订单总数）。', '["fact_order.order_quantity", "fact_order.order_id"]', '["单均商品数", "平均购买件数"]'),
('AVG_AMOUNT_BY_CUSTOMER', '客户平均消费额', '统计周期内客户的平均订单金额（GMV/客户数）。', '["fact_order.order_amount", "fact_order.customer_id"]', '["客均消费", "客户平均下单金额"]'),
-- 会员等级相关
('GMV_BY_MEMBER_LEVEL', '各会员等级GMV', '按客户会员等级（member_level）统计的成交总额。', '["fact_order.order_amount", "dim_customer.member_level"]', '["会员等级销售额", "各等级成交总额"]'),
-- 时间维度类
('DAILY_GMV', '日成交总额', '按日期维度（date_id/year/month/day）统计的每日GMV。', '["fact_order.order_amount", "dim_date.date_id", "dim_date.year", "dim_date.month", "dim_date.day"]', '["日GMV", "每日成交总额"]'),
('QUARTERLY_SALES', '季度销量', '按季度（quarter）统计的商品销售总量。', '["fact_order.order_quantity", "dim_date.quarter"]', '["季度销售件数", "季度销量"]'),
-- 品牌/商品类
('GMV_BY_BRAND', '品牌成交总额', '按商品品牌（brand）统计的成交总额。', '["fact_order.order_amount", "dim_product.brand"]', '["品牌GMV", "各品牌销售额"]'),
('TOP_PRODUCT_SALES', '热销商品销量', '按商品名称（product_name）排序的商品销售数量TOP榜。', '["fact_order.order_quantity", "dim_product.product_id", "dim_product.product_name"]', '["商品销量TOP", "热销商品件数"]');

-- 2. 客户类分析指标
INSERT INTO metric_info (id, name, description, relevant_columns, alias)
VALUES
('CUSTOMER_COUNT', '客户总数', '统计周期内下单的客户总数量，按customer_id去重计数。', '["fact_order.customer_id"]', '["下单客户数", "客户数量"]'),
('CUSTOMER_COUNT_BY_GENDER', '各性别客户数', '按客户性别（gender）统计的下单客户数量。', '["fact_order.customer_id", "dim_customer.gender"]', '["性别客户数", "男女下单人数"]'),
('MEMBER_LEVEL_COUNT', '各会员等级客户数', '按会员等级（member_level）统计的下单客户数量。', '["fact_order.customer_id", "dim_customer.member_level"]', '["会员等级客户数", "各等级下单人数"]');




-- 关联订单类指标与对应列
INSERT INTO column_metric (column_id, metric_id)
VALUES
-- 订单数量类
('fact_order.order_id', 'ORDER_COUNT'),
('fact_order.order_id', 'ORDER_COUNT_BY_REGION'),
('dim_region.region_id', 'ORDER_COUNT_BY_REGION'),
-- 销量类
('fact_order.order_quantity', 'SALES_QUANTITY'),
('fact_order.order_quantity', 'SALES_QUANTITY_BY_CATEGORY'),
('dim_product.category', 'SALES_QUANTITY_BY_CATEGORY'),
-- 客单价/消费能力类
('fact_order.order_quantity', 'AVG_ORDER_QUANTITY'),
('fact_order.order_id', 'AVG_ORDER_QUANTITY'),
('fact_order.order_amount', 'AVG_AMOUNT_BY_CUSTOMER'),
('fact_order.customer_id', 'AVG_AMOUNT_BY_CUSTOMER'),
-- 会员等级相关
('fact_order.order_amount', 'GMV_BY_MEMBER_LEVEL'),
('dim_customer.member_level', 'GMV_BY_MEMBER_LEVEL'),
-- 时间维度类
('fact_order.order_amount', 'DAILY_GMV'),
('dim_date.date_id', 'DAILY_GMV'),
('fact_order.order_quantity', 'QUARTERLY_SALES'),
('dim_date.quarter', 'QUARTERLY_SALES'),
-- 品牌/商品类
('fact_order.order_amount', 'GMV_BY_BRAND'),
('dim_product.brand', 'GMV_BY_BRAND'),
('fact_order.order_quantity', 'TOP_PRODUCT_SALES'),
('dim_product.product_id', 'TOP_PRODUCT_SALES'),
-- 客户类
('fact_order.customer_id', 'CUSTOMER_COUNT'),
('fact_order.customer_id', 'CUSTOMER_COUNT_BY_GENDER'),
('dim_customer.gender', 'CUSTOMER_COUNT_BY_GENDER'),
('fact_order.customer_id', 'MEMBER_LEVEL_COUNT'),
('dim_customer.member_level', 'MEMBER_LEVEL_COUNT');
-- ----------------------------
-- Table structure for table_info
-- ----------------------------
DROP TABLE IF EXISTS `table_info`;
CREATE TABLE `table_info`  (
  `id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '表编号',
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '表名称',
  `role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '表类型(fact/dim)',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '表描述',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of table_info
-- ----------------------------
INSERT INTO `table_info` VALUES ('dim_customer', 'dim_customer', 'dim', '客户维度表，描述下单客户的基本属性。');
INSERT INTO `table_info` VALUES ('dim_date', 'dim_date', 'dim', '时间维度表，用于多时间粒度分析。');
INSERT INTO `table_info` VALUES ('dim_product', 'dim_product', 'dim', '商品维度表，描述商品的基本属性信息。');
INSERT INTO `table_info` VALUES ('dim_region', 'dim_region', 'dim', '地区维度表，用于描述订单发生的地理区域信息。');
INSERT INTO `table_info` VALUES ('fact_order', 'fact_order', 'fact', '订单事实表，记录订单数量和金额等核心指标。');

SET FOREIGN_KEY_CHECKS = 1;
