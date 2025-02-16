import joblib

class MLSignalRefiner:
    def __init__(self):
        self.model = joblib.load('ml_models/signal_model.pkl')

    def refine_signal(self, features):
        return self.model.predict([features])[0]