import pandas as pd
import os
from fashion_clip.fashion_clip import FashionCLIP
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm
import numpy as np
from PIL import Image
import argparse

# Configuration
DATASET_PATH = "/Users/bsama/Downloads/fashion-dataset"
IMAGES_DIR = os.path.join(DATASET_PATH, "images")
STYLES_CSV = os.path.join(DATASET_PATH, "styles.csv")
IMAGES_CSV = os.path.join(DATASET_PATH, "images.csv")
QDRANT_PATH = "/Users/bsama/ai-ecommerce-drilldown/data/qdrant_storage"
COLLECTION_NAME = "fashion_products"
BATCH_SIZE = 64

def ingest(limit=None):
    # 1. Load Data
    print("Loading CSV files...")
    styles_df = pd.read_csv(STYLES_CSV, on_bad_lines='skip')
    images_df = pd.read_csv(IMAGES_CSV)
    
    # Merge on ID
    # styles_df['id'] is int, images_df['filename'] is '1234.jpg'
    images_df['id'] = images_df['filename'].str.replace('.jpg', '', regex=False).astype(int)
    df = pd.merge(styles_df, images_df, on='id')
    
    if limit:
        df = df.head(limit)
        print(f"Limiting ingestion to first {limit} products.")
    
    print(f"Total products to ingest: {len(df)}")

    # 2. Initialize Qdrant
    client = QdrantClient(path=QDRANT_PATH)
    
    # Check if collection exists, if not create it
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if not exists:
        print(f"Creating collection: {COLLECTION_NAME}")
        # FashionCLIP-apple/fashion-clip has 512 dimensions (CLIP VIT-B/32)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
        )

    # 3. Initialize FashionCLIP
    print("Loading FashionCLIP...")
    fclip = FashionCLIP('fashion-clip')

    # 4. Ingest in Batches
    for i in tqdm(range(0, len(df), BATCH_SIZE)):
        batch_df = df.iloc[i : i + BATCH_SIZE]
        
        # Filter out images that don't exist
        valid_paths = []
        valid_indices = []
        for idx, row in batch_df.iterrows():
            img_path = os.path.join(IMAGES_DIR, row['filename'])
            if os.path.exists(img_path):
                valid_paths.append(img_path)
                valid_indices.append(idx)
        
        if not valid_paths:
            continue
            
        # Generate Embeddings
        # FashionCLIP's encode_images takes a list of image paths
        embeddings = fclip.encode_images(valid_paths, batch_size=BATCH_SIZE)
        
        # Prepare Points
        points = []
        for j, idx in enumerate(valid_indices):
            row = df.loc[idx]
            
            # Clean up payload (remove NaN)
            payload = row.to_dict()
            payload = {k: v for k, v in payload.items() if pd.notna(v)}
            
            points.append(models.PointStruct(
                id=int(row['id']),
                vector=embeddings[j].tolist(),
                payload=payload
            ))
            
        # Upsert to Qdrant
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )

    print("Ingestion complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of items to ingest")
    args = parser.parse_args()
    ingest(limit=args.limit)
