#!/usr/bin/env python3
"""
Modulo compartido para la arquitectura LSTM.
Todas las referencias a TinyLSTM / EnhancedLSTM deben importar desde aqui.
Esto evita drift arquitectural entre train, predict y walkforward.
"""

try:
    import torch.nn as nn
except ImportError:
    nn = None


if nn is not None:
    class TinyLSTM(nn.Module):
        """
        LSTM minimalista (confirmador de senal) - modelo legacy.
        - 1 capa, 32 hidden units, ~1.2k parametros.
        - Input: secuencia de close prices z-scored (batch, seq, 1).
        - Output: retorno esperado proximo paso (batch, 1).
        """
        def __init__(self, hidden: int = 32):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden, num_layers=1, batch_first=True)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            o, _ = self.lstm(x)
            return self.head(o[:, -1, :])

    class EnhancedLSTM(nn.Module):
        """
        LSTM mejorado con multi-feature input y dropout.
        - Input: (batch, seq, input_size) con input_size features.
        - Features: close_z, volume_z, atr_norm, rsi_norm, log_return
        - Dropout para regularizacion.
        - Output: retorno esperado proximo paso (batch, 1).
        """
        def __init__(self, input_size: int = 5, hidden: int = 48, dropout: float = 0.15):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden,
                num_layers=2,
                batch_first=True,
                dropout=dropout if hidden > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):
            o, _ = self.lstm(x)
            last = self.dropout(o[:, -1, :])
            return self.head(last)
else:
    TinyLSTM = None  # type: ignore[assignment,misc]
    EnhancedLSTM = None  # type: ignore[assignment,misc]
