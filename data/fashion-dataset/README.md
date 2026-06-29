# Fashion dataset (ecommerce mode)

Place the [fashion-dataset](https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-dataset) files here:

```text
data/fashion-dataset/
├── images/
│   └── {id}.jpg
├── styles.csv
└── images.csv
```

Then ingest into Qdrant (from `drilldown-unified/`):

```bash
cp ../.env.example .env   # set GOOGLE_API_KEY for identify after ingest
python3 scripts/ingest_fashion_dataset.py --limit 1000   # dev subset
python3 scripts/ingest_fashion_dataset.py                # full dataset
```

Vectors are stored in `data/qdrant_storage/`. Product thumbnails are served from `data/fashion-dataset/images/` via `/dataset/{id}.jpg`.
