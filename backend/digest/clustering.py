
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from sklearn.cluster import KMeans

from src.digest.load_chunks import ChunkRow

@dataclass
class ChunkWithCluster:
    
    chunk: ChunkRow
    cluster_id: int

def cluster_chunks(
    chunks: List[ChunkRow],
    n_clusters: int = 15,
    random_state: int = 42,
) -> Tuple[List[ChunkWithCluster], np.ndarray]:
    
    if not chunks:
        return [], np.array([])

valid = [c for c in chunks if c.embedding is not None and len(c.embedding) > 0]
    if not valid:
        return [], np.array([])

X = np.array([c.embedding for c in valid], dtype=np.float64)
    n = X.shape[0]
    k = min(n_clusters, n)
    if k < 1:
        return [], np.array([])

kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(X)
    centroids = kmeans.cluster_centers_

    result: List[ChunkWithCluster] = [
        ChunkWithCluster(chunk=c, cluster_id=int(labels[i]))
        for i, c in enumerate(valid)
    ]
    return result, centroids

def get_typical_chunks_for_cluster(
    chunk_with_cluster: List[ChunkWithCluster],
    centroids: np.ndarray,
    cluster_id: int,
    max_chunks: int = 5,
) -> List[ChunkRow]:
    
    subset = [cwc for cwc in chunk_with_cluster if cwc.cluster_id == cluster_id]
    if not subset or centroids.size == 0 or cluster_id >= centroids.shape[0]:
        return [cwc.chunk for cwc in subset[:max_chunks]]

center = centroids[cluster_id]
    vecs = np.array([cwc.chunk.embedding for cwc in subset], dtype=np.float64)
    if vecs.size == 0:
        return [cwc.chunk for cwc in subset[:max_chunks]]

dists = np.linalg.norm(vecs - center, axis=1)
    order = np.argsort(dists)
    chosen = [subset[i].chunk for i in order[:max_chunks]]
    return chosen
