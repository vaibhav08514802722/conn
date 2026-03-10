# 🚀 Law Chatbot Deployment Guide

## **Deployment Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│              Vercel (Next.js) - FREE TIER                       │
│            https://law-chatbot.vercel.app                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ API Calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND API                              │
│             Render (FastAPI) - FREE TIER                        │
│         https://law-chatbot-api.onrender.com                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              ┌─────────┬──────────┬─────────┐
              │ MongoDB │  Qdrant  │  Redis  │
              │  Atlas  │  Cloud   │  Cloud  │
              │  (FREE) │  (FREE)  │ (Upstash│
              └─────────┴──────────┴─────────┘
```

---

## **Prerequisites**

1. **GitHub account** (already have it ✓)
2. **Groq API key** - Get free key at https://console.groq.com/keys
3. **Vercel account** - Sign up at https://vercel.com
4. **Render account** - Sign up at https://render.com
5. **MongoDB Atlas account** - Sign up at https://www.mongodb.com/cloud/atlas/register
6. **Qdrant Cloud account** - Sign up at https://cloud.qdrant.io

---

## **Step 1: Setup Cloud Databases**

### **A. MongoDB Atlas (Free Tier)**

1. Go to https://www.mongodb.com/cloud/atlas/register
2. Create a free M0 cluster (512 MB storage, enough for thousands of chats)
3. Choose cloud provider: **AWS** and region closest to you
4. Cluster name: `law-chatbot`
5. Wait 5-10 minutes for provisioning
6. Click **"Connect"** → **"Connect your application"**
7. Copy connection string:
   ```
   mongodb+srv://username:<password>@cluster0.xxxxx.mongodb.net/lawchatbot?retryWrites=true&w=majority
   ```
8. Replace `<password>` with your actual database password
9. Add your IP to whitelist: **0.0.0.0/0** (allow from anywhere)

**Save this:** Your `MONGO_URI`

---

### **B. Qdrant Cloud (Free Tier)**

1. Go to https://cloud.qdrant.io
2. Click **"Get Started"** → Sign up with GitHub
3. Create a new cluster:
   - Name: `law-chatbot`
   - Cloud: **AWS** or **GCP**
   - Region: Closest to you
   - Plan: **Free** (1GB storage, 1M vectors)
4. Wait for cluster to provision (~2 minutes)
5. Go to **"Data Access"** → **"API Keys"**
6. Create an API key, copy it
7. Copy the cluster URL (e.g., `https://xxxxx.us-east-1-0.aws.cloud.qdrant.io:6333`)

**Save these:**
- `QDRANT_URL`: The cluster URL
- `QDRANT_API_KEY`: Your API key

---

### **C. Redis (Upstash - Free Tier)**

1. Go to https://upstash.com
2. Sign up with GitHub
3. Click **"Create Database"**
   - Name: `law-chatbot-queue`
   - Type: **Redis**
   - Region: Closest to you
   - Plan: **Free** (10K commands/day)
4. Copy the **Redis URL** (e.g., `redis://default:xxxxx@us1-xxxxx.upstash.io:6379`)

**Save this:** Your `REDIS_URL`

---

## **Step 2: Deploy Backend to Render**

### **Option A: Using render.yaml (Recommended)**

1. Go to https://render.com/dashboard
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repo: `vaibhav08514802722/conn`
4. Render will auto-detect `render.yaml`
5. Set the **Root Directory** to: `law-chatbot`
6. Click **"Apply"**
7. Set environment variables:
   - `GROQ_API_KEY`: `gsk_...` (from Groq console)
   - `MONGO_URI`: `mongodb+srv://...` (from MongoDB Atlas)
   - `QDRANT_URL`: `https://...` (from Qdrant Cloud)
   - `QDRANT_API_KEY`: Your Qdrant API key
   - `JWT_SECRET`: Click **"Generate"** (Render auto-creates)
   - `REDIS_URL`: `redis://...` (from Upstash)
8. Click **"Create Web Service"**
9. Wait 5-10 minutes for build and deploy

**Your backend URL:** `https://law-chatbot-api.onrender.com`

### **Option B: Manual Setup**

1. Go to https://render.com/dashboard
2. Click **"New +"** → **"Web Service"**
3. Connect GitHub repo: `vaibhav08514802722/conn`
4. Configure:
   - **Name:** `law-chatbot-api`
   - **Root Directory:** `law-chatbot`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Add environment variables (same as Option A)
6. Click **"Create Web Service"**

---

### **Update Backend deps.py for Qdrant Cloud**

After deployment, you need to update the Qdrant connection to support API key:

```python
# In backend/deps.py, replace get_qdrant_client() with:
def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        # Support both local and cloud Qdrant
        if settings.qdrant_api_key:
            _qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
        else:
            _qdrant_client = QdrantClient(url=settings.qdrant_url)

        # Auto-create collection if missing
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            _qdrant_client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"✓ Qdrant collection '{settings.qdrant_collection}' created")
        else:
            print(f"✓ Qdrant collection '{settings.qdrant_collection}' ready")

    return _qdrant_client
```

And add `qdrant_api_key` to `backend/config.py`:

```python
class Settings(BaseSettings):
    # ... existing fields ...
    qdrant_api_key: str = ""  # Add this line
```

---

## **Step 3: Deploy Frontend to Vercel**

### **A. Update Frontend Environment**

1. Edit `frontend/.env.local` (or create it):
   ```env
   NEXT_PUBLIC_API_URL=https://law-chatbot-api.onrender.com
   ```

2. Update `frontend/next.config.mjs`:
   ```javascript
   /** @type {import('next').NextConfig} */
   const nextConfig = {
     env: {
       NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
     },
     eslint: {
       ignoreDuringBuilds: true,
     },
     typescript: {
       ignoreBuildErrors: true,
     },
   };

   export default nextConfig;
   ```

### **B. Deploy to Vercel**

1. Go to https://vercel.com/new
2. Import your GitHub repo: `vaibhav08514802722/conn`
3. Configure:
   - **Framework Preset:** Next.js
   - **Root Directory:** `law-chatbot/frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
4. Add environment variable:
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: `https://law-chatbot-api.onrender.com` (your Render backend URL)
5. Click **"Deploy"**
6. Wait 2-3 minutes

**Your frontend URL:** `https://law-chatbot-xxxx.vercel.app`

---

## **Step 4: Update Backend CORS**

After deploying frontend, update backend to allow your Vercel domain:

1. Go to Render dashboard → Your service → **Environment**
2. Add environment variable:
   - Key: `ALLOWED_ORIGINS`
   - Value: `https://law-chatbot-xxxx.vercel.app,http://localhost:3000`

Or update `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://law-chatbot-xxxx.vercel.app",  # Your actual Vercel domain
        "https://*.vercel.app",  # Allow all Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then commit and push to trigger redeployment.

---

## **Step 5: Seed the Database**

After backend is deployed, you need to populate Qdrant with law data:

### **Option A: Run locally with cloud databases**

1. Update your local `.env` with production database URLs:
   ```env
   MONGO_URI=mongodb+srv://...  # Your MongoDB Atlas URL
   QDRANT_URL=https://...       # Your Qdrant Cloud URL
   QDRANT_API_KEY=...           # Your Qdrant API key
   ```

2. Run seed script:
   ```bash
   cd law-chatbot
   python -m scripts.seed_laws
   ```

### **Option B: Create a Render Job**

1. In Render dashboard, go to your service
2. Click **"Shell"** (top right)
3. Run:
   ```bash
   python -m scripts.seed_laws
   ```

---

## **Step 6: Test Your Deployment**

1. Open your Vercel frontend: `https://law-chatbot-xxxx.vercel.app`
2. Sign up for an account
3. Go to chat page
4. Ask: "What is Section 302 IPC?"
5. Should get response with citations!

---

## **Troubleshooting**

### **Backend Deploy Failing**

1. Check Render logs: Dashboard → Service → **Logs**
2. Common issues:
   - **Missing dependencies:** Add to `requirements.txt`
   - **Port error:** Render sets `$PORT` automatically
   - **Timeout:** Free tier spins down after 15 min inactivity, first request takes 30s

### **Frontend Not Connecting to Backend**

1. Check `NEXT_PUBLIC_API_URL` in Vercel environment variables
2. Ensure backend CORS allows your Vercel domain
3. Check browser console for errors (F12 → Console)

### **Database Connection Errors**

1. **MongoDB:** Ensure IP whitelist includes `0.0.0.0/0`
2. **Qdrant:** Check API key is set correctly
3. **Redis:** Free tier has rate limits (10K req/day)

### **Groq API 401 Error**

1. Verify `GROQ_API_KEY` in Render environment variables
2. Test key: https://console.groq.com/keys
3. Free tier: 30 requests/min, 1000/day

---

## **Cost Breakdown (All FREE!)**

| Service | Plan | Limits | Cost |
|---------|------|--------|------|
| **Render (Backend)** | Free | 750 hrs/month, sleeps after 15 min | $0 |
| **Vercel (Frontend)** | Hobby | 100 GB bandwidth, unlimited requests | $0 |
| **MongoDB Atlas** | M0 Free | 512 MB storage | $0 |
| **Qdrant Cloud** | Free | 1 GB, 1M vectors | $0 |
| **Upstash Redis** | Free | 10K commands/day | $0 |
| **Groq API** | Free | 30 req/min, 1000/day | $0 |
| **Total** | | | **$0/month** |

---

## **Production Considerations**

For a production app, consider upgrading:

1. **Render:** Paid tier ($7/month) - No sleep, better performance
2. **MongoDB Atlas:** M10 cluster ($0.08/hour) - Better performance, backups
3. **Qdrant Cloud:** Paid tier ($25/month) - More storage, faster queries
4. **Groq:** Pay-as-you-go - No rate limits
5. **Add monitoring:** Sentry for error tracking

---

## **Environment Variables Summary**

### **Backend (Render)**
```
GROQ_API_KEY=gsk_...
MONGO_URI=mongodb+srv://...
QDRANT_URL=https://...
QDRANT_API_KEY=...
REDIS_URL=redis://...
JWT_SECRET=<auto-generated>
QDRANT_COLLECTION=law_documents
MONGO_DB=lawchatbot
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_MODEL=llama-3.3-70b-versatile
```

### **Frontend (Vercel)**
```
NEXT_PUBLIC_API_URL=https://law-chatbot-api.onrender.com
```

---

## **Continuous Deployment**

Both Render and Vercel support auto-deployment:

1. Make changes locally
2. Commit: `git commit -m "Update feature"`
3. Push: `git push origin master`
4. **Render** auto-deploys backend (2-5 min)
5. **Vercel** auto-deploys frontend (1-2 min)

---

## **Alternative Deployment Options**

### **Railway.app (All-in-one)**
- Deploy backend + databases in one place
- Auto-detects Procfile
- Free tier: $5 credit/month
- https://railway.app

### **Fly.io**
- Good for containerized apps
- Free tier: 3 VMs
- https://fly.io

### **DigitalOcean App Platform**
- $5/month static sites
- $12/month backend apps
- https://www.digitalocean.com/products/app-platform

---

**Need Help?** Check logs first, then open an issue on GitHub!

Good luck with your deployment! 🚀
