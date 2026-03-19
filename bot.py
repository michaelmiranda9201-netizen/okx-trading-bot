# bot_grid_okx.py
import ccxt
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import time
import logging
from datetime import datetime
import os

# Configuración de logging simple
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OKXMicroGridBot:
    def __init__(self):
        # Configuración optimizada para 50 USDT
        self.api_key = os.getenv('db75d70b-f577-40e5-b06c-60b9c87584a7')
        self.api_secret = os.getenv('DD0B0C2024162F50F4267C1D59C4AC81')
        self.password = os.getenv('WXcv8089@')
        self.symbol = 'BTC/USDT'
        
        # Parámetros ultra-conservadores para 50 USDT
        self.total_capital = 50  # USDT
        self.grid_levels = 5  # Reducido para capital pequeño
        self.investment_per_grid = 8  # 8 USDT por grid (40 USDT total, dejando 10 de reserva)
        self.leverage = 2  # Apalancamiento bajo
        self.max_drawdown = 0.05  # 5% máximo drawdown
        
        # Inicializar exchange
        self.exchange = ccxt.okx({
            'apiKey': self.api_key,
            'apiSecret': self.api_secret,
            'password': self.password,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Modelo ML simplificado
        self.model = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.model_trained = False
        self.initial_equity = 50
        
    def calculate_position_size(self, price):
        """Calcula tamaño de posición seguro para 50 USDT"""
        position_value = self.investment_per_grid * self.leverage
        amount = position_value / price
        # Redondear a cantidad permitida por OKX
        return self.exchange.amount_to_precision(self.symbol, amount)
    
    def get_simple_features(self, df):
        """Features simplificados para ML"""
        # Solo indicadores esenciales
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatilidad simple
        df['volatility'] = df['close'].pct_change().rolling(20).std()
        
        return df.dropna()
    
    def train_light_model(self):
        """Entrena modelo ligero"""
        try:
            # Obtener datos
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, '15m', 500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Features
            df = self.get_simple_features(df)
            
            if len(df) < 50:
                return False
            
            # Preparar datos
            features = ['sma_20', 'sma_50', 'rsi', 'volatility']
            X = df[features].values[-200:]
            
            # Target: 1 si sube en próximas 3 velas
            future_returns = df['close'].shift(-3) / df['close'] - 1
            y = (future_returns > 0).astype(int).values[-200:]
            
            # Limpiar datos
            valid_idx = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
            X, y = X[valid_idx], y[valid_idx]
            
            if len(X) > 30:
                X_scaled = self.scaler.fit_transform(X)
                self.model.fit(X_scaled, y)
                self.model_trained = True
                logger.info("Modelo entrenado")
                return True
        except Exception as e:
            logger.error(f"Error entrenando: {e}")
        return False
    
    def predict_trend(self):
        """Predice tendencia simple"""
        if not self.model_trained:
            return 0.5
        
        try:
            # Datos recientes
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, '15m', 50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = self.get_simple_features(df)
            
            features = ['sma_20', 'sma_50', 'rsi', 'volatility']
            latest = df[features].iloc[-1:].values
            
            latest_scaled = self.scaler.transform(latest)
            proba = self.model.predict_proba(latest_scaled)[0]
            
            return proba[1]  # Probabilidad alcista
        except:
            return 0.5
    
    def calculate_safe_grid(self):
        """Grid ultra-conservador"""
        ticker = self.exchange.fetch_ticker(self.symbol)
        current_price = ticker['last']
        
        # Tendencia
        trend = self.predict_trend()
        
        # Ajuste por tendencia (máximo 2% de sesgo)
        if trend > 0.6:
            center = current_price * 1.01
        elif trend < 0.4:
            center = current_price * 0.99
        else:
            center = current_price
        
        # Grid muy ajustado (1% de separación)
        grid_step = center * 0.01  # 1% entre niveles
        half_range = (self.grid_levels // 2) * grid_step
        
        lower = max(center - half_range, center * 0.97)  # Máximo 3% abajo
        upper = min(center + half_range, center * 1.03)  # Máximo 3% arriba
        
        return np.linspace(lower, upper, self.grid_levels).tolist()
    
    def place_safe_orders(self):
        """Coloca órdenes con tamaño seguro"""
        try:
            # Cancelar órdenes previas
            orders = self.exchange.fetch_open_orders(self.symbol)
            for order in orders:
                self.exchange.cancel_order(order['id'], self.symbol)
            
            # Nuevo grid
            grid_prices = self.calculate_safe_grid()
            
            # Colocar órdenes
            for i, price in enumerate(grid_prices):
                amount = self.calculate_position_size(price)
                
                if float(amount) * price <= self.investment_per_grid * 1.1:  # Control de riesgo
                    if i % 2 == 0:
                        self.exchange.create_limit_buy_order(
                            self.symbol, amount, price
                        )
                        logger.info(f"Orden compra: {price} - {amount}")
                    else:
                        self.exchange.create_limit_sell_order(
                            self.symbol, amount, price
                        )
                        logger.info(f"Orden venta: {price} - {amount}")
                        
        except Exception as e:
            logger.error(f"Error órdenes: {e}")
    
    def check_risk(self):
        """Monitorea riesgo constantemente"""
        try:
            balance = self.exchange.fetch_balance()
            total = balance['total'].get('USDT', 0)
            
            # Drawdown
            dd = (self.initial_equity - total) / self.initial_equity
            if dd > self.max_drawdown:
                logger.warning(f"Drawdown {dd:.2%} > {self.max_drawdown:.2%}")
                # Cancelar todo y esperar
                orders = self.exchange.fetch_open_orders(self.symbol)
                for order in orders:
                    self.exchange.cancel_order(order['id'], self.symbol)
                time.sleep(3600)  # Esperar 1 hora
                
            logger.info(f"Balance: ${total:.2f} | DD: {dd:.2%}")
            
        except Exception as e:
            logger.error(f"Error riesgo: {e}")
    
    def run(self):
        """Loop principal"""
        logger.info("Iniciando bot micro-grid (50 USDT)")
        
        # Entrenar modelo
        self.train_light_model()
        
        # Grid inicial
        self.place_safe_orders()
        
        # Variables de control
        last_train = time.time()
        
        while True:
            try:
                # Monitorear riesgo (cada minuto)
                self.check_risk()
                
                # Rebalancear si necesario
                orders = self.exchange.fetch_open_orders(self.symbol)
                if len(orders) < self.grid_levels * 0.5:  # Menos del 50% órdenes activas
                    logger.info("Rebalanceando grid...")
                    self.place_safe_orders()
                
                # Reentrenar cada 6 horas
                if time.time() - last_train > 21600:  # 6 horas
                    self.train_light_model()
                    last_train = time.time()
                
                time.sleep(60)  # Check cada minuto
                
            except KeyboardInterrupt:
                logger.info("Deteniendo bot...")
                orders = self.exchange.fetch_open_orders(self.symbol)
                for order in orders:
                    self.exchange.cancel_order(order['id'], self.symbol)
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(300)

if __name__ == "__main__":
    bot = OKXMicroGridBot()
    bot.run()