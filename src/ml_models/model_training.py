import numpy as np
import pandas as pd
import joblib
import logging
import os
import time
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report, precision_recall_curve
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.pipeline import Pipeline
from scipy.stats import randint
from exchange import Exchange  # Your exchange class
from ml_models.feature_engineering import preprocess_data

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('model_training.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class MLTraining:
    def __init__(self):
        self.model = None
        self.scaler = RobustScaler()  # More robust to outliers
        self.exchange = Exchange()
        self.best_params = None
        self.feature_importance = None

    def fetch_historical_data(self, symbol, timeframe, days=365):
        """Fetch historical data from exchange with dynamic time range handling"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            all_data = []
            
            while start_time < end_time:
                data = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=int(start_time.timestamp() * 1000),
                    limit=1000
                )
                if not data:
                    break
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                all_data.append(df)
                start_time = df['timestamp'].iloc[-1] + pd.Timedelta(milliseconds=1)
                time.sleep(0.1)  # Rate limit protection

            return pd.concat(all_data).drop_duplicates().reset_index(drop=True)
        except Exception as e:
            logger.error(f"Historical data fetch failed: {str(e)}")
            return pd.DataFrame()

    def create_rolling_features(self, data, windows=[3, 7, 14]):
        """Advanced feature engineering with multiple rolling windows"""
        for window in windows:
            data[f'ret_{window}d'] = data['close'].pct_change(window)
            data[f'volatility_{window}d'] = data['close'].pct_change().rolling(window).std()
        return data.dropna()

    def train_model(self, symbol='BTC/USDT', timeframe='1d', retrain_interval=7):
        """Automated retraining pipeline with hyperparameter optimization"""
        try:
            # 1. Data Acquisition
            raw_data = self.fetch_historical_data(symbol, timeframe)
            if raw_data.empty:
                raise ValueError("No data retrieved from exchange")
                
            # 2. Feature Engineering
            data = preprocess_data(raw_data)
            data = self.create_rolling_features(data)
            
            # 3. Label Engineering with triple barrier method
            data['future_return'] = data['close'].pct_change(3).shift(-3)
            data['label'] = np.select(
                [
                    data['future_return'] > 0.02,
                    data['future_return'] < -0.02
                ],
                [1, -1],
                default=0
            )
            
            # 4. Feature Selection
            feature_columns = [col for col in data.columns if col not in ['timestamp', 'label', 'future_return']]
            X = data[feature_columns]
            y = data['label']
            
            # 5. Hyperparameter Optimization
            param_dist = {
                'n_estimators': randint(50, 200),
                'max_depth': [None] + list(np.arange(5, 30, 5)),
                'min_samples_split': randint(2, 11),
                'class_weight': [None, 'balanced']
            }
            
            self.model = RandomizedSearchCV(
                estimator=RandomForestClassifier(random_state=42),
                param_distributions=param_dist,
                n_iter=20,
                cv=5,
                scoring='f1_weighted',
                n_jobs=-1
            )
            
            # 6. Pipeline with Robust Scaling
            pipeline = Pipeline([
                ('scaler', self.scaler),
                ('classifier', self.model)
            ])
            
            pipeline.fit(X, y)
            
            # 7. Save Best Model
            self.best_params = self.model.best_params_
            joblib.dump(pipeline, 'trading_model.pkl')
            
            # 8. Advanced Metrics
            y_pred = pipeline.predict(X)
            logger.info(classification_report(y, y_pred))
            
            # 9. Feature Importance Tracking
            self.feature_importance = pd.Series(
                pipeline.named_steps['classifier'].best_estimator_.feature_importances_,
                index=feature_columns
            ).sort_values(ascending=False)
            
            logger.info("Top 10 Features:\n" + str(self.feature_importance.head(10)))
            
            # 10. Model Versioning
            self._version_model(data.shape[0], symbol, timeframe)
            
        except Exception as e:
            logger.error(f"Training failed: {str(e)}")
            raise

    def _version_model(self, samples, symbol, timeframe):
        """Model versioning with metadata"""
        version_info = {
            'timestamp': datetime.now().isoformat(),
            'samples': samples,
            'symbol': symbol,
            'timeframe': timeframe,
            'features': list(self.feature_importance.index),
            'params': self.best_params
        }
        with open('model_version.json', 'a') as f:
            f.write(json.dumps(version_info) + '\n')

    def predict(self, live_data):
        """Real-time prediction with uncertainty estimation"""
        try:
            pipeline = joblib.load('trading_model.pkl')
            live_data = preprocess_data(live_data)
            live_data = self.create_rolling_features(live_data)
            
            # Ensure feature alignment
            expected_features = pipeline.named_steps['classifier'].best_estimator_.feature_names_in_
            missing = set(expected_features) - set(live_data.columns)
            if missing:
                raise ValueError(f"Missing features: {missing}")
                
            # Generate predictions with probabilities
            probas = pipeline.predict_proba(live_data[expected_features])
            predictions = pipeline.predict(live_data[expected_features])
            
            return {
                'signal': predictions[-1],
                'confidence': np.max(probas[-1]),
                'features': live_data.iloc[-1].to_dict(),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            return {'error': str(e)}

    def monitor_drift(self, window=30):
        """Concept drift detection using feature distributions"""
        # Compare recent feature stats with training data
        # Implement KL divergence or population stability index
        pass

# Advanced Usage Example
if __name__ == "__main__":
    trainer = MLTraining()
    
    # Initial training
    trainer.train_model(symbol='BTC/USDT', timeframe='4h')
    
    # Continuous monitoring
    while True:
        new_data = trainer.fetch_historical_data('BTC/USDT', '4h', days=1)
        if not new_data.empty:
            prediction = trainer.predict(new_data)
            logger.info(f"Live prediction: {prediction}")
            
            # Retrain weekly
            if datetime.now().weekday() == 0:  # Every Monday
                trainer.train_model()
                
        time.sleep(3600)  # Hourly updates