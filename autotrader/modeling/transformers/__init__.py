"""
Transformer models for time-series prediction.

This module implements attention-based sequence models:
- Multi-head self-attention
- Positional encoding
- Encoder-decoder architecture

Key Classes
-----------
TransformerModel : Transformer-based predictor
TransformerConfig : Configuration for transformers

Requirements
------------
pip install torch scikit-learn

References
----------
- Vaswani et al. (2017): "Attention Is All You Need"
"""

from typing import Optional
import numpy as np
from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not available. Install with: pip install torch")

# Import SequenceDataset from sequential module
if TORCH_AVAILABLE:
    from ..sequential import SequenceDataset


@dataclass
class TransformerConfig:
    """Configuration for transformer models."""
    sequence_length: int = 50
    d_model: int = 64
    nhead: int = 4
    num_encoder_layers: int = 2
    dim_feedforward: int = 256
    dropout: float = 0.1
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    early_stopping_patience: int = 10
    device: str = 'cuda' if TORCH_AVAILABLE and torch.cuda.is_available() else 'cpu'


if TORCH_AVAILABLE:
    class PositionalEncoding(nn.Module):
        """Positional encoding for transformer."""
        
        def __init__(self, d_model: int, max_len: int = 5000):
            super().__init__()
            
            position = torch.arange(max_len).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2) * (-np.log(10000.0) / d_model)
            )
            
            pe = torch.zeros(max_len, 1, d_model)
            pe[:, 0, 0::2] = torch.sin(position * div_term)
            pe[:, 0, 1::2] = torch.cos(position * div_term)
            
            self.register_buffer('pe', pe)
        
        def forward(self, x):
            """
            Parameters
            ----------
            x : Tensor
                Shape: (sequence_length, batch_size, d_model)
            """
            return x + self.pe[:x.size(0)]


    class TransformerNetwork(nn.Module):
        """Transformer neural network."""
        
        def __init__(
            self,
            input_size: int,
            d_model: int,
            nhead: int,
            num_encoder_layers: int,
            dim_feedforward: int,
            output_size: int,
            dropout: float = 0.1
        ):
            super().__init__()
            
            self.d_model = d_model
            
            # Input projection
            self.input_proj = nn.Linear(input_size, d_model)
            
            # Positional encoding
            self.pos_encoder = PositionalEncoding(d_model)
            
            # Transformer encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                batch_first=False
            )
            
            self.transformer_encoder = nn.TransformerEncoder(
                encoder_layer,
                num_layers=num_encoder_layers
            )
            
            # Output projection
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(d_model, output_size)
        
        def forward(self, x):
            """
            Parameters
            ----------
            x : Tensor
                Shape: (batch_size, sequence_length, input_size)
            """
            # Project input
            x = self.input_proj(x)  # (batch, seq, d_model)
            
            # Transpose for transformer: (seq, batch, d_model)
            x = x.transpose(0, 1)
            
            # Add positional encoding
            x = self.pos_encoder(x)
            
            # Apply transformer
            x = self.transformer_encoder(x)
            
            # Take last time step: (batch, d_model)
            x = x[-1, :, :]
            
            # Output projection
            x = self.dropout(x)
            x = self.fc(x)
            
            return x


class TransformerModel:
    """
    Transformer model for time series prediction.
    
    Uses multi-head self-attention to capture dependencies in
    sequential data without recurrence.
    
    Parameters
    ----------
    config : TransformerConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = TransformerModel(config=TransformerConfig(
    ...     sequence_length=50,
    ...     d_model=64,
    ...     nhead=4,
    ...     num_encoder_layers=2
    ... ))
    >>> model.fit(X_train, y_train, X_val, y_val)
    >>> predictions = model.predict(X_test)
    
    References
    ----------
    - Vaswani et al. (2017): "Attention Is All You Need"
    """
    
    def __init__(self, config: Optional[TransformerConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. Install with: pip install torch")
        
        self.config = config or TransformerConfig()
        self.model = None
        self.scaler_X = None
        self.is_fitted = False
        self.history = {'train_loss': [], 'val_loss': []}
    
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
        
        self.model = TransformerNetwork(
            input_size=input_size,
            d_model=self.config.d_model,
            nhead=self.config.nhead,
            num_encoder_layers=self.config.num_encoder_layers,
            dim_feedforward=self.config.dim_feedforward,
            output_size=output_size,
            dropout=self.config.dropout
        )
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
            np.zeros(len(X)),
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


# Export public API
__all__ = [
    'TransformerModel',
    'TransformerConfig',
]
