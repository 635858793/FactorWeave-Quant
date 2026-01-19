import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, RFE
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from loguru import logger

def optimize_features_with_pca(X, variance_threshold=0.95):
    """
    使用PCA优化特征集

    参数:
        X: 特征矩阵
        variance_threshold: 保留方差的阈值

    返回:
        X_pca: 降维后的特征矩阵
        pca: 训练好的PCA模型，可用于转换新数据
    """
    # 标准化数据（PCA对特征尺度敏感）
    X_std = (X - X.mean(axis=0)) / X.std(axis=0)

    # 创建PCA模型
    pca = PCA()

    # 拟合模型
    pca.fit(X_std)

    # 计算累积方差比例
    cumulative_variance = np.cumsum(pca.explained_variance_ratio_)

    # 确定需要的主成分数量
    n_components = np.argmax(cumulative_variance >= variance_threshold) + 1

    # 使用确定的主成分数量创建新的PCA模型
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_std)

    logger.info(f"原始特征数量: {X.shape[1]}")
    logger.info(f"PCA后的特征数量: {X_pca.shape[1]}")
    logger.info(f"保留的方差比例: {pca.explained_variance_ratio_.sum():.4f}")

    return X_pca, pca

def enhanced_feature_selection(X, y):
    """
    增强型特征选择

    参数:
        X: 特征矩阵
        y: 目标向量

    返回:
        selected_features: 选择的特征索引列表
        feature_importance: 特征重要性得分DataFrame
    """
    try:
        # 检查输入数据
        if X.shape[0] != len(y):
            raise ValueError("特征矩阵和目标向量长度不匹配")

        # 获取特征名称
        if isinstance(X, pd.DataFrame):
            feature_names = X.columns.tolist()
            X_values = X.values
        else:
            # 如果输入不是DataFrame，设置默认特征名称
            X_values = X
            feature_names = [f'feature_{i}' for i in range(X.shape[1])]

        # 初始化特征选择结果存储
        selection_results = {}

        # 特征重要性评分函数
        def compute_feature_scores(method_name, scorer, X, y):
            """计算特定方法的特征重要性分数"""
            if method_name == 'f_classif':
                # F统计量
                selector = SelectKBest(score_func=scorer, k='all')
                selector.fit(X, y)
                scores = selector.scores_
            elif method_name == 'mutual_info':
                # 互信息
                selector = SelectKBest(score_func=scorer, k='all')
                selector.fit(X, y)
                scores = selector.scores_
            elif method_name == 'random_forest':
                # 随机森林特征重要性
                model = RandomForestClassifier(
                    n_estimators=100, random_state=42)
                model.fit(X, y)
                scores = model.feature_importances_
            elif method_name == 'recursive_elimination':
                # 递归特征消除
                model = RandomForestClassifier(
                    n_estimators=50, random_state=42)
                selector = RFE(model, n_features_to_select=1, step=1)
                selector.fit(X, y)
                scores = np.flip(
                    np.array(range(1, len(selector.ranking_) + 1)) / len(selector.ranking_))
                # 调整ranks以匹配其他方法（较高的分数表示更重要）
                for i, rank in enumerate(selector.ranking_):
                    scores[i] = 1 - (rank - 1) / max(selector.ranking_)
            else:
                raise ValueError(f"未知的特征选择方法: {method_name}")

            # 标准化分数以便于比较（0-1范围）
            if np.sum(scores) > 0:  # 避免除以零
                scores = scores / np.max(scores)

            return scores

        # 1. 使用各种方法评估特征重要性
        logger.info("正在计算特征重要性...")

        # F检验（对于分类问题）
        f_scores = compute_feature_scores('f_classif', f_classif, X_values, y)
        selection_results['f_classif'] = f_scores

        # 互信息（对于非线性关系更有效）
        mi_scores = compute_feature_scores(
            'mutual_info', mutual_info_classif, X_values, y)
        selection_results['mutual_info'] = mi_scores

        # 随机森林特征重要性
        rf_scores = compute_feature_scores('random_forest', None, X_values, y)
        selection_results['random_forest'] = rf_scores

        # 递归特征消除
        rfe_scores = compute_feature_scores(
            'recursive_elimination', None, X_values, y)
        selection_results['recursive_elimination'] = rfe_scores

        # 2. 组合不同方法的结果
        # 计算各种方法的平均分数
        combined_scores = np.zeros(X_values.shape[1])
        for method, scores in selection_results.items():
            combined_scores += scores
        combined_scores /= len(selection_results)

        # 3. 特征稳定性分析
        logger.info("正在进行特征稳定性分析...")
        n_iterations = 5  # 稳定性分析的迭代次数
        stability_scores = np.zeros(X_values.shape[1])

        # 使用交叉验证进行稳定性分析
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        # 定义每次迭代计算特征稳定性的函数
        def compute_stability_iteration(i):
            fold_scores = []
            for train_idx, test_idx in cv.split(X_values, y):
                X_train, y_train = X_values[train_idx], y[train_idx]
                fold_importance = compute_feature_scores(
                    'random_forest', None, X_train, y_train)
                fold_scores.append(fold_importance)
            return fold_scores

        # 计算所有迭代的稳定性得分
        all_fold_scores = []
        for i in range(n_iterations):
            fold_scores = compute_stability_iteration(i)
            all_fold_scores.extend(fold_scores)

        # 计算每个特征的标准差（较低的标准差表示更稳定）
        stability_std = np.std(all_fold_scores, axis=0)
        if np.max(stability_std) > 0:
            # 将稳定性转换为分数（1 - 归一化标准差）
            stability_scores = 1 - stability_std / np.max(stability_std)

        # 4. 结合稳定性和重要性得分
        final_scores = (combined_scores * 0.7) + (stability_scores * 0.3)

        # 5. 整合结果并排序
        feature_importance = pd.DataFrame({
            'feature': feature_names,
            'f_classif': selection_results['f_classif'],
            'mutual_info': selection_results['mutual_info'],
            'random_forest': selection_results['random_forest'],
            'recursive_elimination': selection_results['rfe_scores'] if 'rfe_scores' in selection_results else selection_results['recursive_elimination'],
            'combined_score': combined_scores,
            'stability_score': stability_scores,
            'final_score': final_scores
        })

        # 按最终得分排序
        feature_importance = feature_importance.sort_values(
            'final_score', ascending=False)

        # 6. 选择前k个特征
        k = min(50, X_values.shape[1])  # 设置一个合理的特征数量上限

        # 确定阈值：选择得分至少为最高得分的30%的特征
        threshold = max(0.3 * feature_importance['final_score'].max(), 0.05)
        selected_features = feature_importance[feature_importance['final_score'] >= threshold]

        if len(selected_features) < 5:
            # 如果选择的特征太少，至少保留5个或所有特征
            k = min(5, X_values.shape[1])
            selected_features = feature_importance.head(k)

        logger.info(f"特征选择完成！从{X_values.shape[1]}个特征中选择了{len(selected_features)}个")
        logger.info("选择的前10个特征:")
        for i, (index, row) in enumerate(selected_features.head(10).iterrows()):
            logger.info(f"{i+1}. {row['feature']} (分数: {row['final_score']:.4f})")

        # 返回选择的特征索引和完整的特征重要性DataFrame
        selected_indices = []
        for feature in selected_features['feature']:
            selected_indices.append(feature_names.index(feature))

        return selected_indices, feature_importance

    except Exception as e:
        logger.info(f"特征选择过程出错: {e}")
        # 发生错误时返回所有特征的索引（相当于不进行选择）
        return list(range(X.shape[1])), None

def integrate_enhanced_features(df):
    """
    集成所有增强特征

    参数:
        df: 输入DataFrame

    返回:
        DataFrame: 添加了所有特征的DataFrame
    """
    # 检查基础指标是否已计算
    has_basic_indicators = 'MA5' in df.columns
    has_advanced_indicators = 'macd' in df.columns

    # 如果未计算基础指标，先计算
    from .basic_indicators import calculate_base_indicators, create_advanced_nonlinear_features, create_time_series_features
    from .advanced_indicators import calculate_advanced_indicators
    from .advanced_indicators import create_pattern_recognition_features, create_market_regime_features

    if not has_basic_indicators:
        logger.info("计算基础技术指标...")
        df = calculate_base_indicators(df)

    if not has_advanced_indicators:
        logger.info("计算高级技术指标...")
        df = calculate_advanced_indicators(df)

    # 集成所有特征工程函数
    logger.info("创建高级非线性特征...")
    df = create_advanced_nonlinear_features(df)

    logger.info("创建时间序列特征...")
    df = create_time_series_features(df)

    logger.info("创建K线形态识别特征...")
    df = create_pattern_recognition_features(df)

    logger.info("创建市场状态特征...")
    df = create_market_regime_features(df)

    # 删除重复的列
    df = df.loc[:, ~df.columns.duplicated()]

    return df

def select_features_pca(X, n_components=10):
    """
    使用主成分分析(PCA)进行特征降维

    参数:
        X: 特征DataFrame或矩阵
        n_components: 保留的主成分数量

    返回:
        list: 选中的特征名称
    """
    # 检查输入
    if isinstance(X, pd.DataFrame):
        feature_names = X.columns
        X_values = X.values
    else:
        feature_names = [f"feature_{i}" for i in range(X.shape[1])]
        X_values = X

    # 标准化数据
    X_std = (X_values - np.mean(X_values, axis=0)) / np.std(X_values, axis=0)

    # 应用PCA
    pca = PCA(n_components=min(n_components, X_std.shape[1]))
    pca.fit(X_std)

    # 获取特征重要性
    components = abs(pca.components_)
    importance = np.sum(components, axis=0)

    # 按重要性排序
    sorted_idx = np.argsort(importance)[::-1]

    # 选择前n个特征
    selected_features = [feature_names[i] for i in sorted_idx[:n_components]]

    # 打印PCA结果
    variance_ratio = pca.explained_variance_ratio_
    total_variance = sum(variance_ratio)
    logger.info(f"PCA选择了{len(selected_features)}个特征，解释了{total_variance:.2%}的方差")

    return selected_features

def select_features_importance(X, y, n_features=20, model_type='random_forest', random_state=42):
    """
    使用机器学习模型的特征重要性进行特征选择

    参数:
        X: 特征DataFrame
        y: 目标变量
        n_features: 要选择的特征数量
        model_type: 模型类型，'random_forest'或'mutual_info'
        random_state: 随机种子

    返回:
        list: 选中的特征名称
    """
    # 确保X是DataFrame
    if not isinstance(X, pd.DataFrame):
        raise ValueError("X必须是pandas DataFrame")

    # 处理缺失值
    X = X.fillna(X.mean())

    # 选择特征选择方法
    if model_type == 'random_forest':
        # 随机森林特征重要性
        model = RandomForestClassifier(
            n_estimators=100, random_state=random_state)
        model.fit(X, y)

        # 获取特征重要性
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]

        # 选择前n个特征
        selected_features = [X.columns[i] for i in indices[:n_features]]

        # 打印特征重要性
        logger.info("特征重要性排名:")
        for i, feature in enumerate(selected_features[:10]):  # 只显示前10个
            logger.info(f"{i+1}. {feature}: {importances[indices[i]]:.4f}")

    elif model_type == 'mutual_info':
        # 互信息特征选择
        selector = SelectKBest(mutual_info_classif, k=n_features)
        selector.fit(X, y)

        # 获取分数和索引
        scores = selector.scores_
        indices = np.argsort(scores)[::-1]

        # 选择前n个特征
        selected_features = [X.columns[i] for i in indices[:n_features]]

        # 打印特征重要性
        logger.info("互信息排名:")
        for i, feature in enumerate(selected_features[:10]):  # 只显示前10个
            logger.info(f"{i+1}. {feature}: {scores[indices[i]]:.4f}")

    elif model_type == 'f_classif':
        # F检验特征选择
        selector = SelectKBest(f_classif, k=n_features)
        selector.fit(X, y)

        # 获取分数和索引
        scores = selector.scores_
        indices = np.argsort(scores)[::-1]

        # 选择前n个特征
        selected_features = [X.columns[i] for i in indices[:n_features]]

        # 打印特征重要性
        logger.info("F统计量排名:")
        for i, feature in enumerate(selected_features[:10]):  # 只显示前10个
            logger.info(f"{i+1}. {feature}: {scores[indices[i]]:.4f}")

    else:
        raise ValueError(
            "不支持的模型类型，请选择'random_forest'、'mutual_info'或'f_classif'")

    logger.info(f"总共选择了{len(selected_features)}个特征")

    return selected_features

def calculate_feature_correlations(X, threshold=0.7):
    """
    计算特征之间的相关性并识别高度相关的特征

    参数:
        X: 特征DataFrame
        threshold: 相关性阈值

    返回:
        dict: 高度相关的特征对及其相关系数
    """
    # 计算相关矩阵
    corr_matrix = X.corr().abs()

    # 获取上三角矩阵
    upper = corr_matrix.where(
        np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

    # 找出高度相关的特征对
    high_corr = {}
    for col in upper.columns:
        for idx, val in upper[col].items():
            if val > threshold:
                if (idx, col) not in high_corr and (col, idx) not in high_corr:
                    high_corr[(idx, col)] = val

    # 打印结果
    if high_corr:
        logger.info(f"发现{len(high_corr)}对高度相关的特征 (相关性 > {threshold}):")
        for i, ((feat1, feat2), val) in enumerate(sorted(high_corr.items(), key=lambda x: x[1], reverse=True)):
            if i < 10:  # 只显示前10对
                logger.info(f"{feat1} -- {feat2}: {val:.4f}")
    else:
        logger.info(f"未发现高度相关的特征 (相关性 > {threshold})")

    return high_corr

def remove_redundant_features(X, y, threshold=0.7, target_col=None):
    """
    移除冗余特征，保留与目标变量相关性更高的特征

    参数:
        X: 特征DataFrame
        y: 目标变量
        threshold: 相关性阈值
        target_col: 目标列名（如果y是DataFrame）

    返回:
        list: 建议保留的特征列表
    """
    # 创建包含所有特征和目标变量的DataFrame
    if target_col is None:
        target_col = 'target'

    all_data = X.copy()
    all_data[target_col] = y

    # 计算相关矩阵
    corr_matrix = all_data.corr().abs()

    # 计算特征与目标的相关性
    target_corr = corr_matrix[target_col].drop(target_col)

    # 获取特征之间的相关矩阵
    feature_corr = corr_matrix.drop(
        target_col, axis=0).drop(target_col, axis=1)

    # 找出高度相关的特征对
    to_drop = set()
    for i, feat_i in enumerate(feature_corr.columns):
        for j, feat_j in enumerate(feature_corr.columns):
            if i > j:  # 仅检查上三角矩阵
                # 如果特征高度相关
                if feature_corr.loc[feat_i, feat_j] > threshold:
                    # 检查哪个特征与目标的相关性更强
                    drop_feat = feat_i if target_corr[feat_i] < target_corr[feat_j] else feat_j
                    to_drop.add(drop_feat)

    # 保留的特征
    keep_features = [feat for feat in X.columns if feat not in to_drop]

    logger.info(f"原始特征数量: {X.shape[1]}")
    logger.info(f"移除冗余特征后的特征数量: {len(keep_features)}")
    logger.info(f"移除的特征: {list(to_drop)}")

    return keep_features
