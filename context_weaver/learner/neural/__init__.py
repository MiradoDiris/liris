#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Neural Graph Learner Package

Exports principaux pour import simplifié:
    from context_weaver.learner.neural import NeuralLearner, NeuralConfig
"""

from .config import NeuralConfig, HybridConfig
from .feature_extractor import GraphFeatureExtractor
from .models import NeuralGraphLearner, NodeEncoder, StructureTransformer, StructureClassifier
from .dataset import GraphStructureDataset, OnlineLearningBuffer
from .trainer import NeuralGraphLearnerTrainer
from .wrapper import NeuralGraphLearnerWrapper

# Alias pour import simplifié
NeuralLearner = NeuralGraphLearnerWrapper

__all__ = [
    # Config
    'NeuralConfig',
    'HybridConfig',
    
    # Feature extraction
    'GraphFeatureExtractor',
    
    # Models
    'NeuralGraphLearner',
    'NodeEncoder',
    'StructureTransformer',
    'StructureClassifier',
    
    # Data
    'GraphStructureDataset',
    'OnlineLearningBuffer',
    
    # Training
    'NeuralGraphLearnerTrainer',
    
    # Wrapper (interface principale)
    'NeuralGraphLearnerWrapper',
    'NeuralLearner',  # Alias
]

__version__ = '1.0.0'