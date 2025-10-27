"""
Sequential models for time-series prediction.

This module implements deep learning models for sequential data:
- LSTM (Long Short-Term Memory)
- GRU (Gated Recurrent Unit)
- TCN (Temporal Convolutional Network)

These models are designed for financial time series with:
- Proper sequence handling
- Batch training support
- Early stopping
- Model checkpointing

Key Classes
-----------
LSTMModel : LSTM-based predictor
GRUModel : GRU-based predictor
TCNModel : Temporal CNN predictor
SequenceDataset : PyTorch dataset for sequences

Requirements
------------
pip install torch scikit-learn

References
----------
- Hochreiter & Schmidhuber (1997): "Long Short-Term Memory"
- Cho et al. (2014): "Learning Phrase Representations using RNN"
- Bai et al. (2018): "An Empirical Evaluation of Generic Convolutional and Recurrent Networks"
"""

from typing import Optional, Dict, List, Tuple, Literal
import numpy as np
import pandas as pd
from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not available. Install with: pip install torch")


@dataclass
class SequenceConfig:
    """Configuration for sequence models."""
    sequence_length: int = 50
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    early_stopping_patience: int = 10
    device: str = 'cuda' if TORCH_AVAILABLE and torch.cuda.is_available() else 'cpu'


if TORCH_AVAILABLE:
    class SequenceDataset(Dataset):
        """PyTorch dataset for sequence data."""
        
        def __init__(
            self,
            X: np.ndarray,
            y: np.ndarray,
            sequence_length: int
        ):
            """
            Parameters
            ----------
            X : np.ndarray
                Feature array (n_samples, n_features)
            y : np.ndarray
                Target array (n_samples,)
            sequence_length : int
                Length of sequences to create
            """
            self.X = X
            self.y = y
            self.sequence_length = sequence_length
            
            # Calculate valid indices (need enough history)
            self.valid_indices = list(range(sequence_length, len(X)))
        
        def __len__(self):
            return len(self.valid_indices)
        
        def __getitem__(self, idx):
            actual_idx = self.valid_indices[idx]
            
            # Get sequence
            X_seq = self.X[actual_idx - self.sequence_length:actual_idx]
            y_val = self.y[actual_idx]
            
            return (
                torch.FloatTensor(X_seq),
                torch.FloatTensor([y_val]) if isinstance(y_val, (int, float)) else torch.FloatTensor(y_val)
            )


    class LSTMNetwork(nn.Module):
        """LSTM neural network."""
        
        def __init__(
            self,
            input_size: int,
            hidden_size: int,
            num_layers: int,
            output_size: int,
            dropout: float = 0.2
        ):
            super().__init__()
            
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
            
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_size, output_size)
        
        def forward(self, x):
            # x: (batch_size, sequence_length, input_size)
            lstm_out, _ = self.lstm(x)
            
            # Take last time step
            last_output = lstm_out[:, -1, :]
            
            # Dropout and fully connected
            out = self.dropout(last_output)
            out = self.fc(out)
            
            return out


    class GRUNetwork(nn.Module):
        """GRU neural network."""
        
        def __init__(
            self,
            input_size: int,
            hidden_size: int,
            num_layers: int,
            output_size: int,
            dropout: float = 0.2
        ):
            super().__init__()
            
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            
            self.gru = nn.GRU(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
            
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_size, output_size)
        
        def forward(self, x):
            gru_out, _ = self.gru(x)
            last_output = gru_out[:, -1, :]
            out = self.dropout(last_output)
            out = self.fc(out)
            return out


    class TCNBlock(nn.Module):
        """Temporal Convolutional Network block."""
        
        def __init__(
            self,
            in_channels: int,
            out_channels: int,
            kernel_size: int,
            dilation: int,
            dropout: float = 0.2
        ):
            super().__init__()
            
            padding = (kernel_size - 1) * dilation
            
            self.conv1 = nn.Conv1d(
                in_channels,
                out_channels,
                kernel_size,
                padding=padding,
                dilation=dilation
            )
            self.relu1 = nn.ReLU()
            self.dropout1 = nn.Dropout(dropout)
            
            self.conv2 = nn.Conv1d(
                out_channels,
                out_channels,
                kernel_size,
                padding=padding,
                dilation=dilation
            )
            self.relu2 = nn.ReLU()
            self.dropout2 = nn.Dropout(dropout)
            
            # Residual connection
            self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
            self.relu = nn.ReLU()
        
        def forward(self, x):
            # x: (batch_size, channels, sequence_length)
            out = self.conv1(x)
            out = out[:, :, :-self.conv1.padding[0]]  # Remove padding
            out = self.relu1(out)
            out = self.dropout1(out)
            
            out = self.conv2(out)
            out = out[:, :, :-self.conv2.padding[0]]
            out = self.relu2(out)
            out = self.dropout2(out)
            
            # Residual
            res = x if self.downsample is None else self.downsample(x)
            res = res[:, :, -out.size(2):]  # Match sizes
            
            return self.relu(out + res)


    class TCNNetwork(nn.Module):
        """Temporal Convolutional Network."""
        
        def __init__(
            self,
            input_size: int,
            hidden_size: int,
            num_layers: int,
            output_size: int,
            kernel_size: int = 3,
            dropout: float = 0.2
        ):
            super().__init__()
            
            layers = []
            in_channels = input_size
            
            for i in range(num_layers):
                dilation = 2 ** i
                layers.append(
                    TCNBlock(
                        in_channels=in_channels,
                        out_channels=hidden_size,
                        kernel_size=kernel_size,
                        dilation=dilation,
                        dropout=dropout
                    )
                )
                in_channels = hidden_size
            
            self.network = nn.Sequential(*layers)
            self.fc = nn.Linear(hidden_size, output_size)
        
        def forward(self, x):
            # x: (batch_size, sequence_length, input_size)
            # Transpose for Conv1d: (batch_size, input_size, sequence_length)
            x = x.transpose(1, 2)
            
            # Apply TCN
            out = self.network(x)
            
            # Take last time step
            out = out[:, :, -1]
            
            # Fully connected
            out = self.fc(out)
            
            return out


class SequentialModel:
    """
    Base class for sequential models.
    
    Provides common functionality for LSTM, GRU, and TCN models.
    """
    
    def __init__(
        self,
        model_type: Literal['lstm', 'gru', 'tcn'],
        config: Optional[SequenceConfig] = None
    ):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. Install with: pip install torch")
        
        self.model_type = model_type
        self.config = config or SequenceConfig()
        self.model = None
        self.scaler_X = None
        self.scaler_y = None
        self.is_fitted = False
        self.history = {'train_loss': [], 'val_loss': []}
    
    def _create_model(self, input_size: int, output_size: int) -> nn.Module:
        """Create the neural network model."""
        if self.model_type == 'lstm':
            return LSTMNetwork(
                input_size=input_size,
                hidden_size=self.config.hidden_size,
                num_layers=self.config.num_layers,
                output_size=output_size,
                dropout=self.config.dropout
            )
        elif self.model_type == 'gru':
            return GRUNetwork(
                input_size=input_size,
                hidden_size=self.config.hidden_size,
                num_layers=self.config.num_layers,
                output_size=output_size,
                dropout=self.config.dropout
            )
        elif self.model_type == 'tcn':
            return TCNNetwork(
                input_size=input_size,
                hidden_size=self.config.hidden_size,
                num_layers=self.config.num_layers,
                output_size=output_size,
                dropout=self.config.dropout
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None
    ):
        """
        Fit the model.
        
        Parameters
        ----------
        X : np.ndarray
            Training features (n_samples, n_features)
        y : np.ndarray
            Training targets (n_samples,)
        X_val : np.ndarray, optional
            Validation features
        y_val : np.ndarray, optional
            Validation targets
        """
        # Normalize features
        from sklearn.preprocessing import StandardScaler
        
        self.scaler_X = StandardScaler()
        X_scaled = self.scaler_X.fit_transform(X)
        
        # Create dataset
        train_dataset = SequenceDataset(
            X_scaled, y, self.config.sequence_length
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True
        )
        
        # Validation data
        val_loader = None
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler_X.transform(X_val)
            val_dataset = SequenceDataset(
                X_val_scaled, y_val, self.config.sequence_length
            )
            val_loader = DataLoader(
                val_dataset,
                batch_size=self.config.batch_size,
                shuffle=False
            )
        
        # Create model
        input_size = X.shape[1]
        output_size = 1 if len(y.shape) == 1 else y.shape[1]
        
        self.model = self._create_model(input_size, output_size)
        self.model.to(self.config.device)
        
        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate
        )
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.config.epochs):
            # Training
            self.model.train()
            train_loss = 0.0
            
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.config.device)
                y_batch = y_batch.to(self.config.device)
                
                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            train_loss /= len(train_loader)
            self.history['train_loss'].append(train_loss)
            
            # Validation
            if val_loader is not None:
                self.model.eval()
                val_loss = 0.0
                
                with torch.no_grad():
                    for X_batch, y_batch in val_loader:
                        X_batch = X_batch.to(self.config.device)
                        y_batch = y_batch.to(self.config.device)
                        
                        outputs = self.model(X_batch)
                        loss = criterion(outputs, y_batch)
                        val_loss += loss.item()
                
                val_loss /= len(val_loader)
                self.history['val_loss'].append(val_loss)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                
                if patience_counter >= self.config.early_stopping_patience:
                    print(f"Early stopping at epoch {epoch}")
                    break
                
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{self.config.epochs} - "
                          f"Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")
            else:
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{self.config.epochs} - "
                          f"Train Loss: {train_loss:.6f}")
        
        self.is_fitted = True
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict on new data.
        
        Parameters
        ----------
        X : np.ndarray
            Features (n_samples, n_features)
        
        Returns
        -------
        predictions : np.ndarray
            Predicted values
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        # Scale features
        X_scaled = self.scaler_X.transform(X)
        
        # Create dataset
        dataset = SequenceDataset(
            X_scaled,
            np.zeros(len(X)),  # Dummy targets
            self.config.sequence_length
        )
        loader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=False)
        
        # Predict
        self.model.eval()
        predictions = []
        
        with torch.no_grad():
            for X_batch, _ in loader:
                X_batch = X_batch.to(self.config.device)
                outputs = self.model(X_batch)
                predictions.extend(outputs.cpu().numpy())
        
        return np.array(predictions).flatten()
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probabilities (for classification).
        
        Uses sigmoid activation for binary classification.
        """
        raw_predictions = self.predict(X)
        
        # Apply sigmoid
        probabilities = 1 / (1 + np.exp(-raw_predictions))
        
        # Return as (n_samples, 2) for sklearn compatibility
        return np.column_stack([1 - probabilities, probabilities])


class LSTMModel(SequentialModel):
    """
    LSTM model for time series prediction.
    
    Long Short-Term Memory networks are effective for learning
    long-term dependencies in sequential data.
    
    Parameters
    ----------
    config : SequenceConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = LSTMModel(config=SequenceConfig(
    ...     sequence_length=50,
    ...     hidden_size=64,
    ...     num_layers=2
    ... ))
    >>> model.fit(X_train, y_train, X_val, y_val)
    >>> predictions = model.predict(X_test)
    
    References
    ----------
    - Hochreiter & Schmidhuber (1997): "Long Short-Term Memory"
    """
    
    def __init__(self, config: Optional[SequenceConfig] = None):
        super().__init__('lstm', config)


class GRUModel(SequentialModel):
    """
    GRU model for time series prediction.
    
    Gated Recurrent Units are similar to LSTM but with fewer parameters,
    often leading to faster training.
    
    Parameters
    ----------
    config : SequenceConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = GRUModel(config=SequenceConfig(
    ...     sequence_length=50,
    ...     hidden_size=64,
    ...     num_layers=2
    ... ))
    >>> model.fit(X_train, y_train)
    
    References
    ----------
    - Cho et al. (2014): "Learning Phrase Representations using RNN"
    """
    
    def __init__(self, config: Optional[SequenceConfig] = None):
        super().__init__('gru', config)


class TCNModel(SequentialModel):
    """
    Temporal Convolutional Network for time series prediction.
    
    TCNs use dilated causal convolutions to capture long-range dependencies
    while being more parallelizable than RNNs.
    
    Parameters
    ----------
    config : SequenceConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = TCNModel(config=SequenceConfig(
    ...     sequence_length=50,
    ...     hidden_size=64,
    ...     num_layers=4
    ... ))
    >>> model.fit(X_train, y_train)
    
    References
    ----------
    - Bai et al. (2018): "An Empirical Evaluation of Generic Convolutional
      and Recurrent Networks for Sequence Modeling"
    """
    
    def __init__(self, config: Optional[SequenceConfig] = None):
        super().__init__('tcn', config)


# Export public API
__all__ = [
    'LSTMModel',
    'GRUModel',
    'TCNModel',
    'SequenceConfig',
    'SequenceDataset',
]
