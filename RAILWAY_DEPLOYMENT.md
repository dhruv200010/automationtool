# 🚀 Railway Deployment Guide

## ✅ **What's Ready for Railway**

Your project is now configured for Railway deployment with:
- ✅ **FFmpeg support** via railpack.toml
- ✅ **Web interface** for file uploads (app.py)
- ✅ **Railway-compatible paths** (/app/input, /app/output)
- ✅ **Environment variable support**
- ✅ **Free plan optimization**
- ✅ **Multiple entry points** (app.py, main.py)

## 🚀 **Deployment Steps**

### 1. **Push to GitHub**
```bash
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

### 2. **Deploy on Railway**

1. Go to [railway.app](https://railway.app)
2. Sign up/Login with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose your `automationtool` repository
6. Railway will automatically detect the `railpack.toml` and start building

### 3. **Set Start Command (if needed)**

If Railway still shows "No start command found":
1. Go to your project → **Settings** tab
2. Find **"Start Command"** field
3. Enter: `python app.py`
4. Save and redeploy

### 4. **Set Environment Variables**

In Railway dashboard, go to your project → **Variables** tab and add:

```
OPENROUTER_API_KEY=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
DEEPGRAM_API_KEY=c4183f2d74c789c131cac4dcc7f7a41545d675e2
TELEGRAM_BOT_TOKEN=7951302729:AAEJJZv-C4XX_vewa4PMb0w8gmxjG_O1qjk
```

### 5. **Access Your App**

Once deployed, Railway will give you a URL like:
`https://your-app-name.railway.app`

## 🎬 **How to Use**

1. **Visit your Railway URL**
2. **Upload a video file** (.mp4, .mov, .avi, .mkv)
3. **Wait for processing** (may take 2-5 minutes)
4. **Download processed files** (if any)

## ⚠️ **Free Plan Limitations**

- **1 GB RAM, 1 vCPU** - Keep videos under 100MB for best performance
- **10 GB storage** - Files are temporary (deleted when app stops)
- **5-minute timeout** - Large videos may timeout
- **No persistent storage** - Upload files each time

## 🔧 **Troubleshooting**

### **Build Fails**
- Check Railway logs for errors
- Ensure all files are committed to GitHub
- Verify `railpack.toml` syntax
- If "No start command found" error, Railway should auto-detect `app.py` or `main.py`

### **FFmpeg Not Found**
- Railway should install FFmpeg automatically via railpack
- Check build logs for FFmpeg installation

### **Processing Timeout**
- Try smaller video files (< 50MB)
- Check Railway logs for memory issues

### **File Upload Issues**
- Ensure file is under 100MB
- Check supported formats: .mp4, .mov, .avi, .mkv

## 📊 **Monitoring**

- **Logs**: Check Railway dashboard → Deployments → View Logs
- **Health**: Visit `https://your-app.railway.app/health`
- **Status**: Visit `https://your-app.railway.app/logs`

## 🎯 **Next Steps**

1. **Test with small video** (< 10MB)
2. **Monitor resource usage** in Railway dashboard
3. **Upgrade to paid plan** if you need more resources
4. **Add cloud storage** for persistent file storage

## 💡 **Pro Tips**

- **Start small**: Test with 5-10MB videos first
- **Monitor logs**: Watch Railway logs during processing
- **Use health endpoint**: Check `/health` to verify app is running
- **Keep files small**: Free plan works best with smaller videos

Your video automation pipeline is now ready for Railway! 🎉
