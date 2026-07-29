"""Motore di training "dalle basi" di Gradus.

Niente autograd del framework: forward E backward sono scritti a mano come matmul
ed elementwise. Cosi' gira sulle SOLE operazioni forward (stabili e veloci sulla
RX 6750 via DirectML, dove l'autograd automatico invece sospende il device).

Brick 1: Linear, SiLU, MSE, Adam manuali + gradient-check vs PyTorch.
"""
