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

        # Calculate financial ratios with valid math and clamping to 0..1
        revenue = df['totalRevenue']
        safe_revenue = revenue.replace(0, np.nan)

        df['profit_margin'] = (df['netIncome'] / safe_revenue).fillna(0)
        df['profit_margin'] = np.clip(df['profit_margin'], -1, 1)

        df['gross_margin'] = (df['grossProfit'] / safe_revenue).fillna(0)
        df['gross_margin'] = np.clip(df['gross_margin'], -1, 1)

        df['operating_margin'] = (df['operatingIncome'] / safe_revenue).fillna(0)
        df['operating_margin'] = np.clip(df['operating_margin'], -1, 1)

        # Cost ratios
        df['cost_revenue_ratio'] = (df['costOfRevenue'] / safe_revenue).fillna(0)
        df['cost_revenue_ratio'] = np.clip(df['cost_revenue_ratio'], 0, 1)

        df['expense_ratio'] = (df['totalOperatingExpenses'] / safe_revenue).fillna(0)
        df['expense_ratio'] = np.clip(df['expense_ratio'], 0, 1)

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
            "date": pd.to_datetime(df["date"]).values if "date" in df.columns else None,
            "frequency": df["frequency"].values if "frequency" in df.columns else None
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
        aligned_df['profit_margin'] = np.clip(aligned_df.get('profit_margin', 0), 0, 1)
        aligned_df['gross_margin'] = np.clip(aligned_df.get('gross_margin', 0), 0, 1)
        aligned_df['operating_margin'] = np.clip(aligned_df.get('operating_margin', 0), 0, 1)
        aligned_df['cost_revenue_ratio'] = np.clip(aligned_df.get('cost_revenue_ratio', 0), 0, 1)
        aligned_df['expense_ratio'] = np.clip(aligned_df.get('expense_ratio', 0), 0, 1)
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
        """Train LSTM model for time series prediction with frequency-aware processing"""
        logger.info("Training LSTM model with frequency-aware processing...")

        try:
            # Group by symbol and frequency, then create sequences
            # This ensures quarterly and annual data are handled separately
            sequences = []
            targets = []
            sequence_frequencies = []  # Track frequency for each sequence

            # Check if frequency column exists
            has_frequency = 'frequency' in df.columns

            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol].sort_values('date')

                if has_frequency:
                    # Process quarterly and annual data separately
                    for frequency in ['quarterly', 'annual']:
                        freq_data = symbol_data[symbol_data['frequency'] == frequency].sort_values('date')
                        
                        if len(freq_data) < sequence_length + 1:
                            continue

                        # Prepare features and targets
                        feature_data = freq_data[self.target_columns].values

                        # Create sequences for this frequency
                        for i in range(len(feature_data) - sequence_length):
                            seq = feature_data[i:i + sequence_length]
                            target = feature_data[i + sequence_length]
                            sequences.append(seq)
                            targets.append(target)
                            sequence_frequencies.append(frequency)
                else:
                    # Fallback: process all data together if no frequency column
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
                        sequence_frequencies.append('unknown')

            if len(sequences) == 0:
                logger.warning("Not enough data to create sequences for LSTM training")
                return None

            sequences = np.array(sequences)
            targets = np.array(targets)
            
            # Log frequency distribution
            if has_frequency and sequence_frequencies:
                freq_counts = pd.Series(sequence_frequencies).value_counts()
                logger.info(f"Sequence frequency distribution: {freq_counts.to_dict()}")

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
            try:
                # ✅ FIX: Validate input data before transformation
                if X_new is None or X_new.empty:
                    logger.warning("Empty or None input data provided for prediction")
                    return self._get_default_predictions()
                
                # Check if feature scaler is fitted
                if not hasattr(self.feature_scaler, 'mean_') or self.feature_scaler.mean_ is None:
                    logger.warning("Feature scaler not fitted, using default predictions")
                    return self._get_default_predictions()
                
                # Ensure X_new has the right shape and data types
                if isinstance(X_new, pd.DataFrame):
                    X_new = X_new.fillna(0)  # Fill NaN values
                else:
                    X_new = pd.DataFrame(X_new).fillna(0)
                
                # Check if we have valid numeric data
                if X_new.shape[0] == 0 or X_new.shape[1] == 0:
                    logger.warning("Invalid data shape for prediction")
                    return self._get_default_predictions()
                
                X_scaled = self.feature_scaler.transform(X_new)
                pred_scaled = self.traditional_model.predict(X_scaled)
                pred_original = self.target_scaler.inverse_transform(pred_scaled)

                predictions['traditional'] = {}
                for i, target in enumerate(self.target_columns):
                    predictions['traditional'][target] = float(pred_original[0, i])
                    
            except Exception as e:
                logger.error(f"Prediction error: {str(e)}")
                return self._get_default_predictions()

        return predictions
    
    def _get_default_predictions(self):
        """Return default predictions when model prediction fails"""
        return {
            'traditional': {
                'profit_margin': 0.1,
                'operating_margin': 0.15,
                'cost_revenue_ratio': 0.6,
                'expense_ratio': 0.3
            }
        }


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
        """Comprehensive analysis of income statement data with advanced optimization and date-centered projections"""
        # ✅ LOG: Debug incoming income_data
        logger.info(f"🔍 analyze_income_statement received income_data type: {type(income_data)}")
        if isinstance(income_data, dict):
            logger.info(f"🔍 income_data keys: {list(income_data.keys())}")
            logger.info(f"🔍 income_data sample values: {dict(list(income_data.items())[:10])}")
        elif hasattr(income_data, 'columns'):
            logger.info(f"🔍 income_data columns: {list(income_data.columns)}")
            logger.info(f"🔍 income_data shape: {income_data.shape}")
        
        # Process input data
        processed_data = self._process_input_data(income_data)
        logger.info(f"🔍 After _process_input_data, shape: {processed_data.shape if hasattr(processed_data, 'shape') else 'Unknown'}")

        # Extract date and frequency information for date-centered projections
        statement_date = None
        frequency = None
        
        if isinstance(income_data, dict):
            # Try to extract date from input data
            for date_key in ['date', 'endDate', 'period_date', 'statement_date']:
                if date_key in income_data:
                    try:
                        statement_date = pd.to_datetime(income_data[date_key])
                        break
                    except:
                        pass
            
            # Try to extract frequency
            if 'frequency' in income_data:
                frequency = income_data['frequency']
            elif statement_date is not None:
                # Infer frequency from date (quarterly if month is 3, 6, 9, or 12)
                if statement_date.month in [3, 6, 9, 12]:
                    frequency = 'quarterly'
                else:
                    frequency = 'annual'
        
        # Make predictions
        predictions = self._make_predictions(processed_data)

        # Add date-centered projection information
        if statement_date is not None:
            predictions['projection_date'] = statement_date.isoformat()
            predictions['frequency'] = frequency or 'unknown'
            
            # Calculate next period dates based on frequency
            if frequency == 'quarterly':
                # Next quarter (always 3 months ahead)
                next_date = statement_date + pd.DateOffset(months=3)
                predictions['next_quarter_date'] = next_date.isoformat()
                predictions['next_quarter_year'] = next_date.year
                predictions['next_quarter_quarter'] = ((next_date.month - 1) // 3) + 1
            elif frequency == 'annual':
                # Next year
                next_date = statement_date + pd.DateOffset(years=1)
                predictions['next_annual_date'] = next_date.isoformat()
                predictions['next_annual_year'] = next_date.year

        # Generate recommendations
        recommendations = self._generate_comprehensive_recommendations(processed_data, predictions)

        # Generate risk assessment
        risk_assessment = self._assess_financial_risks(processed_data, predictions)
        
        # ✅ Generate BRUTAL TRUTH REPORT
        truth_report = self._generate_truth_report(income_data, predictions)
        
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
            'truth_report': truth_report,  # ✅ Include truth report in response
            'input_analysis': self._analyze_input_quality(processed_data),
            'confidence_scores': self._calculate_confidence_scores(processed_data, predictions),
            'optimization_analysis': optimization_analysis,
            'date_metadata': {
                'statement_date': statement_date.isoformat() if statement_date is not None else None,
                'frequency': frequency,
                'projection_type': 'quarterly' if frequency == 'quarterly' else ('annual' if frequency == 'annual' else 'unknown')
            }
        }

    def _process_input_data(self, data):
        """Process and validate input data - ensure it's in DataFrame format with date and frequency awareness"""
        # ✅ STRICT MODE: Validate input data is not None or empty
        if data is None:
            raise ValueError("Input data is None - cannot process")
        
        if isinstance(data, dict):
            if not data:
                raise ValueError("Input data dictionary is empty - cannot process")
            df = pd.DataFrame([data])
        else:
            if data is None or (isinstance(data, pd.DataFrame) and data.empty):
                raise ValueError("Input data is None or empty DataFrame - cannot process")
            df = data.copy()

        # Ensure date column exists and is properly formatted
        if 'date' not in df.columns:
            for date_key in ['endDate', 'period_date', 'statement_date']:
                if date_key in df.columns:
                    df['date'] = pd.to_datetime(df[date_key], errors='coerce')
                    break
        
        # Ensure frequency column exists
        if 'frequency' not in df.columns:
            if 'date' in df.columns:
                # Infer frequency from date
                df['frequency'] = df['date'].apply(
                    lambda x: 'quarterly' if pd.notna(x) and x.month in [3, 6, 9, 12] else 'annual'
                )
            else:
                df['frequency'] = 'unknown'

        # The data should already have all features calculated from the view
        # Just ensure it's in the right format
        return df

    def _make_predictions(self, data):
        """Make predictions using trained models"""
        try:
            # ✅ LOG: Debug input data
            logger.info(f"🔍 _make_predictions received data with shape: {data.shape if hasattr(data, 'shape') else 'Unknown'}")
            logger.info(f"🔍 _make_predictions data columns: {list(data.columns) if hasattr(data, 'columns') else 'No columns'}")
            logger.info(f"🔍 _make_predictions data head: {data.head().to_dict() if hasattr(data, 'head') else data}")
            
            # ✅ CRITICAL FIX: Ensure we're using the exact features the model expects
            # The feature_columns should match what was used during training
            expected_features = self.feature_columns
            logger.info(f"🔍 Expected features: {expected_features}")

            # Create a DataFrame with only the expected features
            features_df = pd.DataFrame()

            for feature in expected_features:
                if feature in data.columns:
                    features_df[feature] = data[feature]
                    logger.info(f"✅ Found feature '{feature}' with value: {data[feature].iloc[0] if len(data) > 0 else 'empty'}")
                else:
                    # If feature is missing, set to 0
                    logger.warning(f"⚠️ Feature '{feature}' not found in input data, setting to 0")
                    features_df[feature] = 0

            # Fill any NaN values with 0
            features_df = features_df.fillna(0)
            
            # ✅ LOG: Debug features_df before prediction
            logger.info(f"🔍 features_df shape: {features_df.shape}")
            logger.info(f"🔍 features_df head: {features_df.head().to_dict()}")

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
        """
        ✅ DISABLED: Generic recommendations replaced by truth report
        This method now returns empty recommendations. All real recommendations 
        come from truth_report with specific numbers based on actual financials.
        """
        recommendations = {
            'immediate_actions': [],
            'cost_optimization': [],
            'revenue_enhancement': [],
            'profitability_improvements': [],
            'operational_efficiency': [],
            'strategic_initiatives': []
        }
        
        # ✅ Return empty - truth report handles all recommendations with brutal honesty
        logger.info("✅ Skipping generic recommendations - truth report will provide specific data-driven recommendations")
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
    
    def _generate_truth_report(self, financial_data: Dict[str, Any], predictions: Dict[str, float] | None = None) -> Dict[str, Any]:
        """
        ✅ Generate BRUTAL TRUTH REPORT with specific numbers
        Build a strict-truth report that shows the exact state without sugarcoating.
        """
        def _num(*keys: str) -> float:
            for key in keys:
                if key in financial_data and financial_data[key] is not None:
                    try:
                        return float(financial_data[key])
                    except (ValueError, TypeError):
                        continue
            return 0.0
        
        revenue = _num('totalRevenue', 'total_revenue', 'Revenue', 'revenue')
        cost = _num('costOfRevenue', 'cost_of_revenue', 'cogs')
        gross_profit = _num('grossProfit', 'gross_profit')
        operating_expenses = _num('totalOperatingExpenses', 'total_operating_expenses', 'operatingExpenses')
        operating_income = _num('operatingIncome', 'operating_income')
        net_income = _num('netIncome', 'net_income')
        interest_expense = _num('interestExpense', 'interest_expense')
        taxes = _num('incomeTaxExpense', 'income_tax_expense', 'taxes')
        
        reported = {
            'total_revenue': revenue,
            'cost_of_revenue': cost,
            'gross_profit': gross_profit,
            'operating_expenses': operating_expenses,
            'operating_income': operating_income,
            'net_income': net_income,
            'interest_expense': interest_expense,
            'taxes': taxes
        }
        
        predicted = predictions or {}
        summary_points: List[str] = []
        fraud_flags: List[str] = []
        discrepancies: List[Dict[str, Any]] = []
        honest_recs: List[Dict[str, Any]] = []
        
        def fmt_amount(value: float) -> str:
            return f"KES {value:,.0f}"
        
        summary_points.append(f"Reported revenue: {fmt_amount(revenue)}")
        summary_points.append(f"Reported net income: {fmt_amount(net_income)}")
        summary_points.append(f"Reported operating expenses: {fmt_amount(operating_expenses)}")
        
        # Use the enhanced fraud detection from EnhancedFinancialDataService
        try:
            from Tazama.Services.EnhancedFinancialDataService import EnhancedFinancialDataService
            logger.info("✅ Importing EnhancedFinancialDataService for truth report generation")
            service = EnhancedFinancialDataService()
            full_truth_report = service._generate_truth_report(financial_data, predictions)
            
            # ✅ LOG: Verify truth report was generated
            if full_truth_report and full_truth_report.get('brutally_honest_recommendations'):
                logger.info(f"✅ Truth report generated successfully with {len(full_truth_report['brutally_honest_recommendations'])} recommendations")
                logger.info(f"✅ Truth report keys: {list(full_truth_report.keys())}")
            else:
                logger.warning(f"⚠️ Truth report generated but has no recommendations. Keys: {list(full_truth_report.keys()) if full_truth_report else 'None'}")
            
            return full_truth_report
        except Exception as e:
            logger.error(f"❌ Failed to generate truth report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Return minimal truth report on error
            return {
                'executive_summary': {'overall_risk': 'UNKNOWN', 'summary_points': []},
                'brutally_honest_recommendations': [],
                'fraud_red_flags': [],
                'risk_assessment': {'overall_risk': 'UNKNOWN'},
                'profitability_table': []
            }




