# Deploying to Streamlit Community Cloud

This guide will help you deploy your Route Optimizer app to Streamlit Community Cloud (free hosting).

## Prerequisites

1. A GitHub account
2. Your Google Maps API key

## Step-by-Step Deployment

### 1. Push Your Code to GitHub

First, create a new repository on GitHub and push your code:

```bash
# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Route Optimizer App"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/route-optimizer-app.git

# Push to GitHub
git push -u origin main
```

### 2. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click "New app"
4. Fill in the deployment form:
   - **Repository**: Select your route-optimizer-app repository
   - **Branch**: main
   - **Main file path**: app.py
5. Click "Deploy"

### 3. Add Your Google Maps API Key

After deployment starts:

1. Click on "⋮" (three dots) next to your app
2. Select "Settings"
3. Go to "Secrets" section
4. Add your API key in TOML format:

```toml
GOOGLE_MAPS_API_KEY = "your-actual-api-key-here"
```

5. Click "Save"

### 4. Wait for Deployment

- The app will take 2-5 minutes to deploy
- Once ready, you'll get a URL like: `https://your-app-name.streamlit.app`

## Updating Your App

To update your deployed app:

1. Make changes locally
2. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Update: description of changes"
   git push
   ```
3. The Streamlit app will automatically redeploy

## Troubleshooting

### App Won't Start
- Check the logs in Streamlit Cloud dashboard
- Ensure all dependencies are in requirements.txt
- Verify your Google Maps API key is correctly set in secrets

### Google Maps API Errors
- Make sure your API key has the necessary permissions:
  - Distance Matrix API
  - Geocoding API
- Check that billing is enabled on your Google Cloud account

### Performance Issues
- Streamlit Community Cloud has resource limits
- For production use with many users, consider:
  - Streamlit Teams (paid)
  - Self-hosting on cloud providers

## Alternative Deployment Options

If you need more control or resources:

1. **Railway.app** - Easy deployment with more resources
2. **Render.com** - Free tier available
3. **Google Cloud Run** - Scalable, pay-per-use
4. **AWS EC2** - Full control over infrastructure

## Support

For issues specific to:
- This app: Create an issue on GitHub
- Streamlit deployment: Visit [Streamlit Forums](https://discuss.streamlit.io) 