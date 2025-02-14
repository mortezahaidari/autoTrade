from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import logging
import pandas as pd
import numpy as np
from ml_models.feature_engineering import preprocess_data

logger = logging.getLogger(__name__)

class MLTraining:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)

    def train_model(self, data):
        """Trains the machine learning model."""
        data = preprocess_data(data)  # Ensure data is preprocessed

        data['Future_Price'] = data['close'].shift(-1)
        data['Label'] = np.where(data['Future_Price'] > data['close'], 1, 0)
        data.dropna(inplace=True)

        features = data[['Short_MA', 'Long_MA', 'RSI', 'Upper_Band', 'Lower_Band', 'MACD', 'Signal_Line', '%K', '%D']]
        labels = data['Label']

        X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"✅ Model trained with accuracy: {accuracy:.2f}")

    def predict_signals(self, data):
        """Predicts trading signals using the trained model."""
        data = preprocess_data(data)
        features = data[['Short_MA', 'Long_MA', 'RSI', 'Upper_Band', 'Lower_Band', 'MACD', 'Signal_Line', '%K', '%D']]
        predictions = self.model.predict(features)
        signals = ['buy' if pred == 1 else 'sell' for pred in predictions]
        return signals
