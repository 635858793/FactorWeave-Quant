"""
ai_stock_selector_service.py
AI智能选股服务模块

用法示例：
    selector = AIStockSelector(model_type='ml')
    stock_df = ...  # 股票特征DataFrame
    criteria = {'industry': '科技', '市值_min': 100e8}
    selected = selector.select_stocks(stock_df, criteria)
    for code in selected:
        logger.info(f"{code selector.explain_selection(code}")
"""

from loguru import logger
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


class AIStockSelector:
    """
    智能选股主类，支持多因子、机器学习、深度学习等多种选股方式。

    参数:
        model_type: 选股模型类型（'ml', 'dl', 'factor'等）
        model_params: 模型参数字典
    """

    def __init__(self, model_type: str = 'ml', model_params: Dict[str, Any] = None):
        """
        初始化AI选股器
        :param model_type: 选股模型类型（'ml', 'dl', 'factor'等）
        :param model_params: 模型参数
        """
        self.model_type = model_type
        self.model_params = model_params or {}
        self.model = None
        self.feature_importance = None
        self.is_trained = False
        
        # 初始化模型
        self._init_model()

    def _init_model(self):
        """初始化模型"""
        try:
            if self.model_type == 'ml':
                self._init_ml_model()
            elif self.model_type == 'dl':
                self._init_dl_model()
            elif self.model_type == 'factor':
                self.model = None
                logger.info("使用因子筛选模式")
            else:
                logger.warning(f"未知的模型类型: {self.model_type}，使用因子筛选模式")
                self.model = None
        except Exception as e:
            logger.error(f"初始化模型失败: {e}")
            self.model = None

    def _init_ml_model(self):
        """初始化机器学习模型"""
        try:
            from utils.imports import get_sklearn
            _sklearn_modules = get_sklearn()
            
            if not _sklearn_modules:
                logger.warning("sklearn 不可用，使用因子筛选模式")
                self.model = None
                return
            
            sklearn_ensemble = _sklearn_modules.get('ensemble')
            if sklearn_ensemble:
                RandomForestClassifier = getattr(sklearn_ensemble, 'RandomForestClassifier', None)
                if RandomForestClassifier:
                    self.model = RandomForestClassifier(
                        n_estimators=self.model_params.get('n_estimators', 100),
                        max_depth=self.model_params.get('max_depth', None),
                        min_samples_split=self.model_params.get('min_samples_split', 5),
                        min_samples_leaf=self.model_params.get('min_samples_leaf', 2),
                        max_features=self.model_params.get('max_features', 'sqrt'),
                        bootstrap=True,
                        class_weight='balanced',
                        random_state=42
                    )
                    logger.info("机器学习模型初始化完成: RandomForestClassifier")
                    return
            
            logger.warning("无法初始化 RandomForestClassifier，使用因子筛选模式")
            self.model = None
        except Exception as e:
            logger.error(f"初始化机器学习模型失败: {e}")
            self.model = None

    def _init_dl_model(self):
        """初始化深度学习模型"""
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
            from tensorflow.keras.optimizers import Adam
            from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
            
            # 创建模型
            model = Sequential()
            
            # 输入层
            input_dim = self.model_params.get('input_dim', 10)
            model.add(Dense(128, input_dim=input_dim, activation='relu'))
            model.add(BatchNormalization())
            model.add(Dropout(0.3))
            
            # 隐藏层1
            model.add(Dense(64, activation='relu'))
            model.add(BatchNormalization())
            model.add(Dropout(0.3))
            
            # 隐藏层2
            model.add(Dense(32, activation='relu'))
            model.add(BatchNormalization())
            model.add(Dropout(0.2))
            
            # 输出层（二分类：买入/不买入）
            model.add(Dense(1, activation='sigmoid'))
            
            # 编译模型
            model.compile(
                optimizer=Adam(learning_rate=self.model_params.get('learning_rate', 0.001)),
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
            
            self.model = model
            logger.info("深度学习模型初始化完成: Neural Network")
            
        except ImportError:
            logger.warning("TensorFlow 未安装，使用因子筛选模式")
            self.model = None
        except Exception as e:
            logger.error(f"初始化深度学习模型失败: {e}")
            self.model = None

    def train_model(self, X_train: pd.DataFrame, y_train: pd.Series):
        """
        训练模型
        
        Args:
            X_train: 训练特征数据
            y_train: 训练标签数据
        """
        try:
            if self.model is None:
                logger.warning("模型未初始化，无法训练")
                return
            
            if self.model_type == 'ml':
                self.model.fit(X_train, y_train)
                self.is_trained = True
                
                # 提取特征重要性
                if hasattr(self.model, 'feature_importances_'):
                    self.feature_importance = self.model.feature_importances_
                
                logger.info("机器学习模型训练完成")
                
            elif self.model_type == 'dl':
                # 定义回调函数
                early_stopping = EarlyStopping(
                    monitor='val_loss',
                    patience=10,
                    restore_best_weights=True
                )
                
                reduce_lr = ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.2,
                    patience=5,
                    min_lr=1e-6
                )
                
                # 训练模型
                history = self.model.fit(
                    X_train, y_train,
                    epochs=self.model_params.get('epochs', 100),
                    batch_size=self.model_params.get('batch_size', 32),
                    validation_split=0.2,
                    callbacks=[early_stopping, reduce_lr],
                    verbose=0
                )
                
                self.is_trained = True
                logger.info("深度学习模型训练完成")
                
            else:
                logger.warning(f"模型类型 {self.model_type} 不需要训练")
                
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            self.is_trained = False

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        使用模型进行预测
        
        Args:
            X: 特征数据
            
        Returns:
            预测结果（概率或类别）
        """
        try:
            if self.model is None or not self.is_trained:
                logger.warning("模型未训练，返回全1（全部选中）")
                return np.ones(len(X))
            
            if self.model_type == 'ml':
                # 返回预测概率
                proba = self.model.predict_proba(X)
                return proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]
                
            elif self.model_type == 'dl':
                # 返回预测概率
                proba = self.model.predict(X, verbose=0)
                return proba.flatten()
                
            else:
                logger.warning(f"模型类型 {self.model_type} 不支持预测")
                return np.ones(len(X))
                
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return np.ones(len(X))

    def select_stocks(self, stock_data: pd.DataFrame, criteria: Dict[str, Any]) -> List[str]:
        """
        根据输入数据和选股条件，返回推荐股票列表
        :param stock_data: 股票特征数据（DataFrame，需包含code列）
        :param criteria: 选股条件（如行业、市值、因子阈值等）
        :return: 推荐股票代码列表
        """
        df = self._kdata_preprocess(stock_data, context="AI选股")
        if df is None or df.empty:
            return []
        
        # 行业筛选
        if 'industry' in criteria and criteria['industry']:
            df = df[df['industry'] == criteria['industry']]
        
        # 市值筛选
        if '市值_min' in criteria:
            if 'market_cap' in df.columns:
                df = df[df['market_cap'] >= criteria['市值_min']]
        if '市值_max' in criteria:
            if 'market_cap' in df.columns:
                df = df[df['market_cap'] <= criteria['市值_max']]
        
        # PE筛选
        if 'pe_min' in criteria:
            if 'pe' in df.columns:
                df = df[df['pe'] >= criteria['pe_min']]
        if 'pe_max' in criteria:
            if 'pe' in df.columns:
                df = df[df['pe'] <= criteria['pe_max']]
        
        # PB筛选
        if 'pb_min' in criteria:
            if 'pb' in df.columns:
                df = df[df['pb'] >= criteria['pb_min']]
        if 'pb_max' in criteria:
            if 'pb' in df.columns:
                df = df[df['pb'] <= criteria['pb_max']]
        
        # ROE筛选
        if 'roe_min' in criteria:
            if 'roe' in df.columns:
                df = df[df['roe'] >= criteria['roe_min']]
        if 'roe_max' in criteria:
            if 'roe' in df.columns:
                df = df[df['roe'] <= criteria['roe_max']]
        
        # 如果模型已训练，使用模型预测
        if self.model is not None and self.is_trained:
            try:
                # 提取特征列
                feature_columns = [col for col in df.columns if col not in ['code', 'name', 'industry']]
                if feature_columns:
                    X = df[feature_columns].fillna(0)
                    
                    # 预测
                    proba = self.predict(X)
                    
                    # 设置阈值
                    threshold = criteria.get('threshold', 0.5)
                    
                    # 筛选
                    df = df.copy()
                    df['prediction'] = proba
                    df = df[df['prediction'] >= threshold]
                    
                    logger.info(f"模型预测: 从 {len(stock_data)} 只股票中筛选出 {len(df)} 只")
            except Exception as e:
                logger.error(f"模型预测失败: {e}")
        
        return df['code'].tolist() if 'code' in df.columns else []

    def explain_selection(
        self,
        stock_code: str,
        stock_data: Optional[pd.DataFrame] = None,
        method: str = "feature_importance"
    ) -> str:
        """
        返回指定股票的AI选股理由/因子解释
        :param stock_code: 股票代码
        :param stock_data: 股票特征数据（可选）
        :param method: 解释方法（feature_importance, shap, lime）
        :return: 解释说明
        """
        try:
            if self.model_type == 'factor':
                return "满足多因子筛选条件"
            
            elif self.model_type == 'ml' and self.is_trained:
                # 尝试使用高级可解释性工具
                try:
                    from .model_explainer import ModelExplainer, ExplainabilityMethod
                    
                    if stock_data is not None and not stock_data.empty:
                        # 提取特征列
                        feature_columns = [col for col in stock_data.columns if col not in ['code', 'name', 'industry']]
                        
                        if feature_columns and self.model is not None:
                            # 创建解释器
                            explainer = ModelExplainer(self.model, feature_columns)
                            
                            # 获取股票特征
                            stock_row = stock_data[stock_data['code'] == stock_code]
                            if not stock_row.empty:
                                instance = stock_row[feature_columns].iloc[0]
                                
                                # 根据方法选择解释方式
                                if method == "shap":
                                    from .model_explainer import ExplainabilityMethod
                                    explanation = explainer.explain_with_shap(stock_data[feature_columns])
                                elif method == "lime":
                                    explanation = explainer.explain_with_lime(stock_data[feature_columns], instance)
                                else:
                                    explanation = explainer.explain_with_feature_importance(stock_data[feature_columns])
                                
                                # 生成解释文本
                                return self._format_explanation(explanation, stock_code, instance)
                
                except Exception as e:
                    logger.warning(f"高级可解释性工具失败，使用基础解释: {e}")
                
                # 回退到基础解释
                if self.feature_importance is not None:
                    explanation = f"基于机器学习模型（{type(self.model).__name__}）的选股分析：\n"
                    
                    if stock_data is not None and not stock_data.empty:
                        stock_row = stock_data[stock_data['code'] == stock_code]
                        if not stock_row.empty:
                            feature_columns = [col for col in stock_data.columns if col not in ['code', 'name', 'industry']]
                            if feature_columns:
                                feature_values = stock_row[feature_columns].iloc[0]
                                
                                importance_dict = dict(zip(feature_columns, self.feature_importance))
                                sorted_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
                                
                                explanation += "\n关键特征贡献：\n"
                                for feature, importance in sorted_features[:5]:
                                    value = feature_values.get(feature, 0)
                                    explanation += f"- {feature}: {value:.2f} (重要性: {importance:.3f})\n"
                    
                    return explanation
            
            elif self.model_type == 'dl' and self.is_trained:
                return "基于深度学习模型的选股分析：模型通过多层神经网络学习股票特征，预测该股票具有投资价值"
            
            else:
                return "满足多因子筛选条件"
                
        except Exception as e:
            logger.error(f"生成选股解释失败: {e}")
            return "满足多因子筛选条件"
    
    def _format_explanation(
        self,
        explanation: Any,
        stock_code: str,
        instance: pd.Series
    ) -> str:
        """格式化解释结果
        
        Args:
            explanation: 模型解释结果
            stock_code: 股票代码
            instance: 股票特征
            
        Returns:
            格式化的解释文本
        """
        try:
            result = f"股票 {stock_code} 的选股分析：\n\n"
            result += f"解释方法: {explanation.method}\n"
            result += f"摘要: {explanation.summary}\n\n"
            
            if explanation.feature_explanations:
                result += "关键特征贡献：\n"
                for feat_exp in explanation.feature_explanations[:10]:
                    direction_text = "正向" if feat_exp.direction == "positive" else "负向"
                    result += f"- {feat_exp.feature_name}: {feat_exp.contribution:.4f} ({direction_text})\n"
            
            return result
            
        except Exception as e:
            logger.warning(f"格式化解释失败: {e}")
            return f"股票 {stock_code} 满足选股条件"

    def _kdata_preprocess(self, df: pd.DataFrame, context="分析") -> pd.DataFrame:
        """K线数据预处理"""
        try:
            from utils.data_preprocessing import kdata_preprocess
            return kdata_preprocess(df, context)
        except ImportError:
            # 如果导入失败，返回原数据
            logger.info(f" 无法导入统一的数据预处理模块，使用原数据")
            return df
        except Exception as e:
            logger.info(f"[ERROR] 数据预处理失败: {str(e)}")
            return df

# 后续可扩展：模型训练、自动调参、批量选股等