# tazama_core.py - Core Tazama classes adapted for Django
"""
Core Tazama financial analysis classes adapted for Django integration
This file contains the essential classes from your original tazama.py
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import warnings
from typing import Dict, List, Optional, Tuple, Any
import logging

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Set device for PyTorch
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class FinancialDataProcessor:
    """Enhanced data processor for Django integration"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.feature_columns = []
        self.target_columns = ['profit_margin', 'operating_margin', 'cost_revenue_ratio', 'expense_ratio']

    def _create_financial_features(self, df):
        """Create comprehensive financial features from raw data"""
        # Ensure necessary columns exist
        required_cols = ['totalRevenue', 'netIncome', 'grossProfit', 'operatingIncome',
                         'totalOperatingExpenses', 'costOfRevenue', 'researchDevelopment']

        for col in required_cols:
            if col not in df.columns:
                df[col] = 0

        # Calculate financial ratios
        df['profit_margin'] = df['netIncome'] / (df['totalRevenue'] + 1e-8)
        df['profit_margin'] = np.clip(df['profit_margin'], -1, 1)

        df['gross_margin'] = df['grossProfit'] / (df['totalRevenue'] + 1e-8)
        df['gross_margin'] = np.clip(df['gross_margin'], -1, 1)

        df['operating_margin'] = df['operatingIncome'] / (df['totalRevenue'] + 1e-8)
        df['operating_margin'] = np.clip(df['operating_margin'], -1, 1)

        # Cost ratios
        df['cost_revenue_ratio'] = df['costOfRevenue'] / (df['totalRevenue'] + 1e-8)
        df['cost_revenue_ratio'] = np.clip(df['cost_revenue_ratio'], 0, 2)

        df['expense_ratio'] = df['totalOperatingExpenses'] / (df['totalRevenue'] + 1e-8)
        df['expense_ratio'] = np.clip(df['expense_ratio'], 0, 2)

        # R&D intensity
        df['rd_intensity'] = df['researchDevelopment'] / (df['totalRevenue'] + 1e-8)
        df['rd_intensity'] = np.clip(df['rd_intensity'], 0, 1)

        # Revenue efficiency metrics
        df['revenue_per_expense'] = df['totalRevenue'] / (df['totalOperatingExpenses'] + 1e-8)
        df['revenue_per_expense'] = np.clip(df['revenue_per_expense'], 0, 10)

        self.feature_columns = [
            'profit_margin', 'gross_margin', 'operating_margin',
            'cost_revenue_ratio', 'expense_ratio', 'rd_intensity',
            'revenue_per_expense'
        ]

        return df

    def prepare_features_and_targets(self, df: pd.DataFrame):
        """
        Split features and targets from the dataset
        Returns: X (features), y (targets), metadata (symbol/date)
        """
        if not all(col in df.columns for col in self.feature_columns + self.target_columns):
            missing = set(self.feature_columns + self.target_columns) - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        X = df[self.feature_columns].copy()
        y = df[self.target_columns].copy()

        metadata = {
            "symbol": df["symbol"].values,
            "date": pd.to_datetime(df["date"]).values if "date" in df.columns else None
        }

        return X, y, metadata

    def validate_and_align_features(self, df, expected_features=None):
        """
        Ensure input dataframe has all required features aligned with training
        """
        if expected_features is None:
            expected_features = self.feature_columns

        # Create aligned dataframe
        aligned_df = pd.DataFrame()

        for feature in expected_features:
            if feature in df.columns:
                aligned_df[feature] = df[feature]
            else:
                # Feature missing - calculate if possible or set to 0
                logger.warning(f"Feature '{feature}' missing, attempting to calculate or setting to 0")
                aligned_df[feature] = 0

        # Fill NaN values
        aligned_df = aligned_df.fillna(0)

        # Clip values to training ranges
        aligned_df['profit_margin'] = np.clip(aligned_df.get('profit_margin', 0), -1, 1)
        aligned_df['gross_margin'] = np.clip(aligned_df.get('gross_margin', 0), -1, 1)
        aligned_df['operating_margin'] = np.clip(aligned_df.get('operating_margin', 0), -1, 1)
        aligned_df['cost_revenue_ratio'] = np.clip(aligned_df.get('cost_revenue_ratio', 0), 0, 2)
        aligned_df['expense_ratio'] = np.clip(aligned_df.get('expense_ratio', 0), 0, 2)
        aligned_df['rd_intensity'] = np.clip(aligned_df.get('rd_intensity', 0), 0, 1)
        aligned_df['revenue_per_expense'] = np.clip(aligned_df.get('revenue_per_expense', 0), 0, 10)

        return aligned_df


class FinancialDataset(Dataset):
    """PyTorch dataset for financial time series data"""

    def __init__(self, sequences, targets):
        self.sequences = torch.FloatTensor(sequences)
        self.targets = torch.FloatTensor(targets)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]


class MultiTargetLSTM(nn.Module):
    """Enhanced multi-target LSTM model for financial prediction"""

    def __init__(self, input_size, hidden_size, num_layers, output_size, dropout=0.2):
        super(MultiTargetLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0
        )

        # Attention mechanism
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)

        # Output layers
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.fc2 = nn.Linear(hidden_size // 2, output_size)
        self.activation = nn.ReLU()

    def forward(self, x):
        # LSTM forward pass
        lstm_out, _ = self.lstm(x)

        # Apply attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)

        # Use the last output for prediction
        last_output = attn_out[:, -1, :]

        # Fully connected layers
        out = self.dropout(last_output)
        out = self.activation(self.fc1(out))
        out = self.dropout(out)
        out = self.fc2(out)

        return out


class UnifiedFinancialModels:
    """Unified model system for traditional ML and LSTM models"""

    def __init__(self, target_columns):
        self.target_columns = target_columns
        self.traditional_model = None
        self.lstm_model = None
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.lstm_feature_scaler = StandardScaler()
        self.lstm_target_scaler = StandardScaler()
        self.device = device
        self.training_history = {}

    def train_traditional_models(self, X, y):
        """Train unified traditional ML model"""
        logger.info("Training unified traditional ML model...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features and targets
        X_train_scaled = self.feature_scaler.fit_transform(X_train)
        X_test_scaled = self.feature_scaler.transform(X_test)
        y_train_scaled = self.target_scaler.fit_transform(y_train)
        y_test_scaled = self.target_scaler.transform(y_test)

        # Train multi-output Random Forest
        self.traditional_model = MultiOutputRegressor(
            RandomForestRegressor(
                n_estimators=200,
                max_depth=15,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        )

        self.traditional_model.fit(X_train_scaled, y_train_scaled)

        # Evaluate
        y_pred_scaled = self.traditional_model.predict(X_test_scaled)
        y_pred = self.target_scaler.inverse_transform(y_pred_scaled)

        # Calculate metrics for each target
        metrics = {}
        for i, target in enumerate(self.target_columns):
            r2 = r2_score(y_test.iloc[:, i], y_pred[:, i])
            mse = mean_squared_error(y_test.iloc[:, i], y_pred[:, i])
            mae = mean_absolute_error(y_test.iloc[:, i], y_pred[:, i])

            metrics[target] = {'R2': r2, 'MSE': mse, 'MAE': mae}
            logger.info(f"Traditional {target} - R2: {r2:.4f}, MSE: {mse:.6f}, MAE: {mae:.6f}")

        self.training_history['traditional'] = metrics
        return metrics

    def train_lstm_model(self, df, sequence_length=10, batch_size=32, epochs=50, learning_rate=0.001):
        """Train LSTM model for time series prediction"""
        logger.info("Training LSTM model...")

        try:
            # Group by symbol and create sequences
            sequences = []
            targets = []

            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol].sort_values('date')

                if len(symbol_data) < sequence_length + 1:
                    continue

                # Prepare features and targets
                feature_data = symbol_data[self.target_columns].values

                # Create sequences
                for i in range(len(feature_data) - sequence_length):
                    seq = feature_data[i:i + sequence_length]
                    target = feature_data[i + sequence_length]
                    sequences.append(seq)
                    targets.append(target)

            if len(sequences) == 0:
                logger.warning("Not enough data to create sequences for LSTM training")
                return None

            sequences = np.array(sequences)
            targets = np.array(targets)

            # Scale data
            n_samples, n_timesteps, n_features = sequences.shape
            sequences_reshaped = sequences.reshape(-1, n_features)
            sequences_scaled = self.lstm_feature_scaler.fit_transform(sequences_reshaped)
            sequences_scaled = sequences_scaled.reshape(n_samples, n_timesteps, n_features)

            targets_scaled = self.lstm_target_scaler.fit_transform(targets)

            # Split data
            train_size = int(0.8 * len(sequences_scaled))
            train_sequences = sequences_scaled[:train_size]
            train_targets = targets_scaled[:train_size]
            test_sequences = sequences_scaled[train_size:]
            test_targets = targets_scaled[train_size:]

            # Create datasets and dataloaders
            train_dataset = FinancialDataset(train_sequences, train_targets)
            test_dataset = FinancialDataset(test_sequences, test_targets)

            train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
            test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

            # Initialize model
            input_size = n_features
            hidden_size = 64
            num_layers = 2
            output_size = len(self.target_columns)

            self.lstm_model = MultiTargetLSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                output_size=output_size,
                dropout=0.2
            ).to(self.device)

            # Training setup
            criterion = nn.MSELoss()
            optimizer = optim.Adam(self.lstm_model.parameters(), lr=learning_rate)

            # Training loop
            train_losses = []
            val_losses = []

            for epoch in range(epochs):
                # Training
                self.lstm_model.train()
                epoch_train_loss = 0
                for sequences_batch, targets_batch in train_loader:
                    sequences_batch = sequences_batch.to(self.device)
                    targets_batch = targets_batch.to(self.device)

                    optimizer.zero_grad()
                    outputs = self.lstm_model(sequences_batch)
                    loss = criterion(outputs, targets_batch)
                    loss.backward()
                    optimizer.step()

                    epoch_train_loss += loss.item()

                avg_train_loss = epoch_train_loss / len(train_loader)
                train_losses.append(avg_train_loss)

                # Validation
                self.lstm_model.eval()
                epoch_val_loss = 0
                with torch.no_grad():
                    for sequences_batch, targets_batch in test_loader:
                        sequences_batch = sequences_batch.to(self.device)
                        targets_batch = targets_batch.to(self.device)

                        outputs = self.lstm_model(sequences_batch)
                        loss = criterion(outputs, targets_batch)
                        epoch_val_loss += loss.item()

                avg_val_loss = epoch_val_loss / len(test_loader)
                val_losses.append(avg_val_loss)

                if (epoch + 1) % 10 == 0:
                    logger.info(
                        f"Epoch [{epoch + 1}/{epochs}], Train Loss: {avg_train_loss:.6f}, Val Loss: {avg_val_loss:.6f}")

            # Final evaluation
            self.lstm_model.eval()
            all_predictions = []
            all_targets = []

            with torch.no_grad():
                for sequences_batch, targets_batch in test_loader:
                    sequences_batch = sequences_batch.to(self.device)
                    outputs = self.lstm_model(sequences_batch)
                    all_predictions.append(outputs.cpu().numpy())
                    all_targets.append(targets_batch.numpy())

            predictions = np.vstack(all_predictions)
            actuals = np.vstack(all_targets)

            # Inverse transform
            predictions_original = self.lstm_target_scaler.inverse_transform(predictions)
            actuals_original = self.lstm_target_scaler.inverse_transform(actuals)

            # Calculate metrics
            metrics = {}
            for i, target in enumerate(self.target_columns):
                r2 = r2_score(actuals_original[:, i], predictions_original[:, i])
                mse = mean_squared_error(actuals_original[:, i], predictions_original[:, i])
                mae = mean_absolute_error(actuals_original[:, i], predictions_original[:, i])

                metrics[target] = {'R2': r2, 'MSE': mse, 'MAE': mae}
                logger.info(f"LSTM {target} - R2: {r2:.4f}, MSE: {mse:.6f}, MAE: {mae:.6f}")

            self.training_history['lstm'] = {
                'metrics': metrics,
                'train_losses': train_losses,
                'val_losses': val_losses
            }

            return metrics

        except Exception as e:
            logger.error(f"LSTM training error: {str(e)}")
            return None

    def predict(self, X_new, use_lstm=False):
        """Make predictions using trained models"""
        predictions = {}

        # Traditional model prediction
        if self.traditional_model is not None:
            X_scaled = self.feature_scaler.transform(X_new)
            pred_scaled = self.traditional_model.predict(X_scaled)
            pred_original = self.target_scaler.inverse_transform(pred_scaled)

            predictions['traditional'] = {}
            for i, target in enumerate(self.target_columns):
                predictions['traditional'][target] = float(pred_original[0, i])

        return predictions


class EnhancedFinancialOptimizer:
    """Enhanced optimizer for comprehensive financial analysis with advanced optimization"""

    def __init__(self, models, feature_columns, target_columns):
        self.models = models
        self.feature_columns = feature_columns
        self.target_columns = target_columns
        self.processor = FinancialDataProcessor()
        
        # Import optimization services
        try:
            from Tazama.Services.FinancialOptimizationService import AdvancedFinancialOptimizationService
            self.optimization_service = AdvancedFinancialOptimizationService()
        except ImportError:
            self.optimization_service = None
            logger.warning("FinancialOptimizationService not available")

    def analyze_income_statement(self, income_data):
        """Comprehensive analysis of income statement data with advanced optimization"""
        # Process input data
        processed_data = self._process_input_data(income_data)

        # Make predictions
        predictions = self._make_predictions(processed_data)

        # Generate recommendations
        recommendations = self._generate_comprehensive_recommendations(processed_data, predictions)

        # Generate risk assessment
        risk_assessment = self._assess_financial_risks(processed_data, predictions)
        
        # Advanced optimization analysis
        optimization_analysis = {}
        if self.optimization_service:
            try:
                optimization_analysis = self.optimization_service.comprehensive_financial_optimization(
                    income_data, predictions
                )
            except Exception as e:
                logger.error(f"Optimization analysis failed: {e}")
                optimization_analysis = {'error': str(e)}

        return {
            'predictions': predictions,
            'recommendations': recommendations,
            'risk_assessment': risk_assessment,
            'input_analysis': self._analyze_input_quality(processed_data),
            'confidence_scores': self._calculate_confidence_scores(processed_data, predictions),
            'optimization_analysis': optimization_analysis
        }

    def _process_input_data(self, data):
        """Process and validate input data - ensure it's in DataFrame format"""
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            df = data.copy()

        # The data should already have all features calculated from the view
        # Just ensure it's in the right format
        return df

    def _make_predictions(self, data):
        """Make predictions using trained models"""
        try:
            # ✅ CRITICAL FIX: Ensure we're using the exact features the model expects
            # The feature_columns should match what was used during training
            expected_features = self.feature_columns

            # Create a DataFrame with only the expected features
            features_df = pd.DataFrame()

            for feature in expected_features:
                if feature in data.columns:
                    features_df[feature] = data[feature]
                else:
                    # If feature is missing, set to 0
                    logger.warning(f"Feature '{feature}' not found in input data, setting to 0")
                    features_df[feature] = 0

            # Fill any NaN values with 0
            features_df = features_df.fillna(0)

            # Make predictions
            predictions = self.models.predict(features_df, use_lstm=False)

            # Return traditional predictions or empty dict if failed
            return predictions.get('traditional', {})

        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

            # Return default predictions based on actual values if available
            default_predictions = {}
            for target in self.target_columns:
                if target in data.columns:
                    default_predictions[target] = float(data[target].iloc[0])
                else:
                    default_predictions[target] = 0.0

            return default_predictions

    def _calculate_confidence_scores(self, data, predictions):
        """Calculate confidence scores for predictions"""
        confidence_scores = {}

        for target, value in predictions.items():
            # Simple confidence calculation based on data quality and value reasonableness
            base_confidence = 0.7

            # Adjust confidence based on value reasonableness
            if target in ['profit_margin', 'operating_margin']:
                if -0.5 <= value <= 0.5:  # Reasonable range
                    base_confidence += 0.2
            elif target in ['cost_revenue_ratio', 'expense_ratio']:
                if 0 <= value <= 1.5:  # Reasonable range
                    base_confidence += 0.2

            confidence_scores[target] = min(base_confidence, 1.0)

        return confidence_scores

    def _generate_comprehensive_recommendations(self, data, predictions):
        """Generate detailed optimization recommendations"""
        recommendations = {
            'immediate_actions': [],
            'cost_optimization': [],
            'revenue_enhancement': [],
            'profitability_improvements': [],
            'operational_efficiency': [],
            'strategic_initiatives': []
        }

        # Extract current metrics
        current_revenue = float(data.get('totalRevenue', pd.Series([0])).iloc[0])
        current_profit_margin = predictions.get('profit_margin', 0)
        current_operating_margin = predictions.get('operating_margin', 0)
        current_cost_ratio = predictions.get('cost_revenue_ratio', 0)
        current_expense_ratio = predictions.get('expense_ratio', 0)

        # Generate recommendations based on predictions
        if current_profit_margin < -0.05:
            recommendations['immediate_actions'].append({
                'priority': 'CRITICAL',
                'action': 'Emergency Profitability Review',
                'description': 'Company is experiencing significant losses. Immediate cost reduction and revenue protection measures required.',
                'timeline': '1-2 weeks',
                'impact': 'Business survival'
            })

        if current_cost_ratio > 0.7:
            potential_savings = current_revenue * 0.05
            recommendations['cost_optimization'].append({
                'priority': 'HIGH',
                'action': 'Supply Chain Optimization',
                'description': 'Cost of goods sold is high. Negotiate better supplier terms, optimize inventory management.',
                'potential_savings': f'${potential_savings:,.0f}',
                'timeline': '3-6 months'
            })

        if current_expense_ratio > 0.4:
            recommendations['cost_optimization'].append({
                'priority': 'MEDIUM',
                'action': 'Operational Expense Review',
                'description': 'Operating expenses are elevated. Review administrative costs, eliminate redundancies.',
                'timeline': '2-4 months'
            })

        if current_profit_margin < 0.15 and current_profit_margin > 0:
            recommendations['profitability_improvements'].append({
                'priority': 'HIGH',
                'action': 'Profit Margin Enhancement Program',
                'description': 'Implement comprehensive pricing strategy review and cost management program.',
                'target': '15-20% profit margin',
                'timeline': '6-9 months'
            })

        # Add revenue enhancement recommendations
        if current_revenue > 0:
            recommendations['revenue_enhancement'].append({
                'priority': 'MEDIUM',
                'action': 'Revenue Growth Initiatives',
                'description': 'Focus on expanding market share, customer acquisition, and product diversification.',
                'target': f'Increase revenue by 10-15% to ${current_revenue * 1.15:,.0f}',
                'timeline': '6-12 months'
            })

        return recommendations

    def _assess_financial_risks(self, data, predictions):
        """Comprehensive financial risk assessment"""
        risks = {
            'liquidity_risk': 'LOW',
            'profitability_risk': 'LOW',
            'operational_risk': 'LOW',
            'market_risk': 'MEDIUM',
            'overall_risk': 'LOW',
            'risk_factors': []
        }

        profit_margin = predictions.get('profit_margin', 0)
        operating_margin = predictions.get('operating_margin', 0)
        cost_ratio = predictions.get('cost_revenue_ratio', 0)

        risk_score = 0

        # Profitability risk assessment
        if profit_margin < -0.05:
            risks['profitability_risk'] = 'HIGH'
            risk_score += 3
            risks['risk_factors'].append("Severe profitability issues - immediate attention required")
        elif profit_margin < 0.05:
            risks['profitability_risk'] = 'MEDIUM'
            risk_score += 2
            risks['risk_factors'].append("Low profitability - monitor closely")

        # Operational risk assessment
        if cost_ratio > 0.8:
            risks['operational_risk'] = 'HIGH'
            risk_score += 3
            risks['risk_factors'].append("Very high cost structure - operational efficiency issues")
        elif cost_ratio > 0.7:
            risks['operational_risk'] = 'MEDIUM'
            risk_score += 1
            risks['risk_factors'].append("Elevated costs - optimization opportunities exist")

        # Overall risk determination
        if risk_score >= 5:
            risks['overall_risk'] = 'HIGH'
        elif risk_score >= 3:
            risks['overall_risk'] = 'MEDIUM'

        return risks

    def _analyze_input_quality(self, data):
        """Analyze quality and completeness of input data"""
        analysis = {
            'completeness': 'HIGH',
            'quality_score': 0.9,
            'missing_fields': [],
            'data_issues': [],
            'recommendations': []
        }

        # Check for missing or zero values in critical fields
        critical_fields = ['totalRevenue', 'netIncome', 'operatingIncome']
        for field in critical_fields:
            if field not in data.columns or data[field].iloc[0] == 0:
                analysis['missing_fields'].append(field)
                analysis['quality_score'] -= 0.1

        if analysis['missing_fields']:
            analysis['completeness'] = 'MEDIUM'
            analysis['recommendations'].append(
                "Provide complete financial data for more accurate analysis"
            )

        return analysis




