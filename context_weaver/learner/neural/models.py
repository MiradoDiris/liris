#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Architectures neuronales pour Graph Learner - VERSION CORRIGÉE

✅ AJOUTS:
- GraphAttentionTransformer avec bias structurel
- Attention pondérée par adjacency matrix
- Support pour masques d'attention
"""

import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional
import math

logger = logging.getLogger(__name__)


# ============================================================================
# NODE ENCODER (inchangé)
# ============================================================================

class NodeEncoder(nn.Module):
    """Encode un nœud en représentation vectorielle"""
    
    def __init__(self, input_dim: int, embed_dim: int, dropout: float = 0.1):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, embed_dim * 2),
            nn.LayerNorm(embed_dim * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(embed_dim * 2, embed_dim),
            nn.LayerNorm(embed_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)


# ============================================================================
# 🆕 GRAPH ATTENTION TRANSFORMER
# ============================================================================

class GraphAttentionLayer(nn.Module):
    """
    🆕 Couche d'attention biaisée par la structure du graphe
    
    Combine:
    - Multi-head attention standard
    - Bias structurel depuis adjacency matrix
    - Masquage pour padding
    """
    
    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        use_graph_bias: bool = True
    ):
        super().__init__()
        
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.use_graph_bias = use_graph_bias
        
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        
        # Projections Q, K, V
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        
        # 🆕 Projection pour graph bias
        if use_graph_bias:
            self.graph_bias_proj = nn.Linear(1, num_heads)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)
    
    def forward(
        self,
        x: torch.Tensor,
        adjacency_matrix: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            x: [batch, seq_len, embed_dim]
            adjacency_matrix: [batch, seq_len, seq_len] - 1 si connexion existe
            attention_mask: [batch, seq_len, seq_len] - True pour ignorer
        
        Returns:
            [batch, seq_len, embed_dim]
        """
        batch_size, seq_len, _ = x.shape
        
        # Projections
        q = self.q_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim)
        k = self.k_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim)
        v = self.v_proj(x).view(batch_size, seq_len, self.num_heads, self.head_dim)
        
        # Reshape pour multi-head: [batch, num_heads, seq_len, head_dim]
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        
        # Attention scores: [batch, num_heads, seq_len, seq_len]
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / self.scale
        
        # 🆕 Ajouter bias structurel depuis adjacency
        if self.use_graph_bias and adjacency_matrix is not None:
            # adjacency_matrix: [batch, seq_len, seq_len]
            # On veut: [batch, num_heads, seq_len, seq_len]
            
            # Ajouter dimension pour projection
            adj_expanded = adjacency_matrix.unsqueeze(-1)  # [batch, seq, seq, 1]
            
            # Projeter vers num_heads
            graph_bias = self.graph_bias_proj(adj_expanded)  # [batch, seq, seq, num_heads]
            graph_bias = graph_bias.permute(0, 3, 1, 2)  # [batch, num_heads, seq, seq]
            
            # Amplifier les connexions existantes
            attn_scores = attn_scores + graph_bias * 5.0
        
        # Appliquer masque d'attention (padding)
        if attention_mask is not None:
            # attention_mask: [batch, seq_len, seq_len] - True = ignorer
            attn_scores = attn_scores.masked_fill(
                attention_mask.unsqueeze(1),  # [batch, 1, seq, seq]
                float('-inf')
            )
        
        # Softmax
        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        # Appliquer attention
        attn_output = torch.matmul(attn_weights, v)
        
        # Reshape: [batch, seq_len, embed_dim]
        attn_output = attn_output.transpose(1, 2).contiguous()
        attn_output = attn_output.view(batch_size, seq_len, self.embed_dim)
        
        # Projection finale
        output = self.out_proj(attn_output)
        
        return output


class GraphTransformerEncoderLayer(nn.Module):
    """
    🆕 Couche Transformer complète avec graph attention
    """
    
    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        feedforward_dim: int,
        dropout: float = 0.1,
        use_graph_bias: bool = True
    ):
        super().__init__()
        
        self.self_attn = GraphAttentionLayer(
            embed_dim, num_heads, dropout, use_graph_bias
        )
        
        self.feedforward = nn.Sequential(
            nn.Linear(embed_dim, feedforward_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(feedforward_dim, embed_dim),
            nn.Dropout(dropout)
        )
        
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        x: torch.Tensor,
        adjacency_matrix: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        # Self-attention avec résiduelle
        attn_output = self.self_attn(x, adjacency_matrix, attention_mask)
        x = self.norm1(x + self.dropout(attn_output))
        
        # Feedforward avec résiduelle
        ff_output = self.feedforward(x)
        x = self.norm2(x + ff_output)
        
        return x


class StructureTransformer(nn.Module):
    """
    🆕 CORRIGÉ: Transformer pour capturer les relations entre nœuds
    
    Utilise graph attention pour pondérer selon structure parent-enfant
    """
    
    def __init__(
        self,
        node_embed_dim: int,
        transformer_dim: int,
        num_layers: int,
        num_heads: int,
        feedforward_dim: int,
        dropout: float = 0.1,
        use_graph_bias: bool = True
    ):
        super().__init__()
        
        self.input_projection = nn.Linear(node_embed_dim, transformer_dim)
        
        # Positional encoding (learnable)
        self.pos_encoding = nn.Parameter(
            torch.randn(1, 100, transformer_dim) * 0.02
        )
        
        # 🆕 Couches Graph Transformer
        self.layers = nn.ModuleList([
            GraphTransformerEncoderLayer(
                transformer_dim,
                num_heads,
                feedforward_dim,
                dropout,
                use_graph_bias
            )
            for _ in range(num_layers)
        ])
        
        self.output_projection = nn.Linear(transformer_dim, node_embed_dim)
        self.output_norm = nn.LayerNorm(node_embed_dim)
    
    def forward(
        self,
        node_embeds: torch.Tensor,
        adjacency_matrix: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        node_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            node_embeds: [batch, seq_len, node_embed_dim]
            adjacency_matrix: [batch, seq_len, seq_len]  # 🆕
            attention_mask: [batch, seq_len, seq_len]    # 🆕
            node_mask: [batch, seq_len] (1 = valide, 0 = padding)
        
        Returns:
            [batch, seq_len, node_embed_dim]
        """
        x = self.input_projection(node_embeds)
        
        # Positional encoding
        batch_size, seq_len, _ = x.shape
        x = x + self.pos_encoding[:, :seq_len, :]
        
        # 🆕 Passer par chaque couche avec graph attention
        for layer in self.layers:
            x = layer(x, adjacency_matrix, attention_mask)
        
        # Projection de sortie
        x = self.output_projection(x)
        x = self.output_norm(x)
        
        return x


# ============================================================================
# STRUCTURE CLASSIFIER (inchangé)
# ============================================================================

class StructureClassifier(nn.Module):
    """MLP pour classifier la validité d'une structure"""
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: list,
        dropout: float = 0.2
    ):
        super().__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.classifier = nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(x)


# ============================================================================
# MODÈLE COMPLET
# ============================================================================

class NeuralGraphLearner(nn.Module):
    """
    🆕 CORRIGÉ: Modèle complet avec graph attention
    
    Pipeline:
    1. Encode chaque nœud individuellement
    2. Capture relations avec Graph Transformer
    3. Agrège les embeddings (mean pooling)
    4. Encode le contexte
    5. Fusionne et classifie
    """
    
    def __init__(
        self,
        node_input_dim: int,
        context_input_dim: int,
        config
    ):
        super().__init__()
        
        self.config = config
        
        # Node encoder
        self.node_encoder = NodeEncoder(
            node_input_dim,
            config.node_embed_dim,
            config.dropout
        )
        
        # Context encoder
        self.context_encoder = nn.Sequential(
            nn.Linear(context_input_dim, config.context_embed_dim),
            nn.LayerNorm(config.context_embed_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout)
        )
        
        # 🆕 Graph Transformer
        self.transformer = StructureTransformer(
            node_embed_dim=config.node_embed_dim,
            transformer_dim=config.transformer_dim,
            num_layers=config.num_transformer_layers,
            num_heads=config.num_attention_heads,
            feedforward_dim=config.feedforward_dim,
            dropout=config.dropout,
            use_graph_bias=True  # 🆕 Activer graph bias
        )
        
        # Classifier
        classifier_input_dim = config.node_embed_dim + config.context_embed_dim
        
        self.classifier = StructureClassifier(
            classifier_input_dim,
            config.mlp_hidden_dims,
            config.mlp_dropout
        )
    
    def forward(
        self,
        node_features: torch.Tensor,
        context_features: torch.Tensor,
        adjacency_matrix: Optional[torch.Tensor] = None,  # 🆕
        attention_mask: Optional[torch.Tensor] = None,    # 🆕
        node_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        🆕 CORRIGÉ: Forward avec adjacency et attention mask
        
        Args:
            node_features: [batch, seq_len, node_feature_dim]
            context_features: [batch, context_dim]
            adjacency_matrix: [batch, seq_len, seq_len]  # 🆕
            attention_mask: [batch, seq_len, seq_len]    # 🆕
            node_mask: [batch, seq_len]
        
        Returns:
            validity_scores: [batch, 1]
        """
        batch_size = node_features.size(0)
        seq_len = node_features.size(1)
        
        # 1. Encode nodes
        node_features_flat = node_features.view(-1, node_features.size(-1))
        node_embeds_flat = self.node_encoder(node_features_flat)
        node_embeds = node_embeds_flat.view(batch_size, seq_len, -1)
        
        # 2. Graph Transformer (capture relations)
        contextualized_embeds = self.transformer(
            node_embeds,
            adjacency_matrix,
            attention_mask,
            node_mask
        )
        
        # 3. Aggregate nodes (mean pooling)
        if node_mask is not None:
            mask_expanded = node_mask.unsqueeze(-1)
            sum_embeds = (contextualized_embeds * mask_expanded).sum(dim=1)
            count = node_mask.sum(dim=1, keepdim=True).clamp(min=1)
            aggregated = sum_embeds / count
        else:
            aggregated = contextualized_embeds.mean(dim=1)
        
        # 4. Encode context
        context_embeds = self.context_encoder(context_features)
        
        # 5. Concatenate et classify
        combined = torch.cat([aggregated, context_embeds], dim=-1)
        validity_score = self.classifier(combined)
        
        return validity_score
    
    def get_attention_weights(
        self,
        node_features: torch.Tensor,
        adjacency_matrix: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        node_mask: Optional[torch.Tensor] = None,
        layer_idx: int = -1
    ):
        """
        🆕 Extrait les poids d'attention d'une couche (pour visualisation)
        
        Note: Nécessite de modifier GraphAttentionLayer pour retourner weights
        """
        # TODO: Implémenter extraction
        raise NotImplementedError("Extraction d'attention weights non implémentée")