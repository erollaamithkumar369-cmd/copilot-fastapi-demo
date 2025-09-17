# copilot-fastapi-demo

This repository contains a FastAPI application exposing endpoints for Microsoft Graph users, system health, log management, and event access.
It's pre-configured to be deployed to **Azure App Service (Linux)** using GitHub Actions.

## Project structure
```
copilot-fastapi-demo/
├── main.py
├── requirements.txt
├── startup.txt
└── .github/
    └── workflows/
        └── azure.yml
```

## Prerequisites
- Azure subscription
- GitHub account
- Create an Azure Web App (Linux) with name: **copilot-fastapi-demo** (Python 3.11, Region: West Europe recommended)
- App Service Plan: B1 or S1 recommended

## Setup Steps

1. **Create the GitHub repository** and upload these files (or unzip and push to GitHub).
2. **Create Azure Web App**:
   - Runtime: Python 3.11
   - OS: Linux
   - Name: copilot-fastapi-demo

3. **Add Application Settings (Environment variables)** in Azure Portal (Web App -> Configuration -> Application settings):
   - `TENANT_ID` = your tenant id
   - `CLIENT_ID` = your client id
   - `CLIENT_SECRET` = your client secret
   - (Optional) `DEPLOYED_BASE_URL` = https://copilot-fastapi-demo.azurewebsites.net

4. **Get Publish Profile**:
   - In Azure Portal > Your Web App > Get publish profile (download XML)
   - In GitHub > Repository > Settings > Secrets and variables > Actions > New repository secret
     - Name: `AZURE_WEBAPP_PUBLISH_PROFILE`
     - Value: (paste contents of the downloaded publish profile XML file)

5. **Push to GitHub** (main branch) to trigger GitHub Actions deployment.
6. **Verify**:
   - Open: `https://copilot-fastapi-demo.azurewebsites.net/docs` for FastAPI documentation
   - Open: `https://copilot-fastapi-demo.azurewebsites.net/openapi.json` for OpenAPI schema
   - Plugin manifest: `https://copilot-fastapi-demo.azurewebsites.net/.well-known/ai-plugin.json`

## Notes & Security
- **Do NOT** commit your CLIENT_SECRET or other secrets to the repository. Use Azure App Settings and GitHub Secrets as described.
- For production, consider storing secrets in **Azure Key Vault** and using Managed Identity.
- If you need Windows event access, deploy to a Windows machine / VM with the needed privileges.