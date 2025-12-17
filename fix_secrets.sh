#!/bin/bash
# Script to replace secrets in docker-compose.yml

if [ -f docker-compose.yml ]; then
    # Replace OpenAI API key
    sed -i '' 's|OPENAI_API_KEY: "sk-proj-[^"]*"|OPENAI_API_KEY: ${OPENAI_API_KEY}|g' docker-compose.yml
    
    # Replace Zoho credentials
    sed -i '' 's|ZOHO_CLIENT_ID: "[^"]*"|ZOHO_CLIENT_ID: ${ZOHO_CLIENT_ID}|g' docker-compose.yml
    sed -i '' 's|ZOHO_CLIENT_SECRET: "[^"]*"|ZOHO_CLIENT_SECRET: ${ZOHO_CLIENT_SECRET}|g' docker-compose.yml
    sed -i '' 's|ZOHO_REDIRECT_URI: "[^"]*"|ZOHO_REDIRECT_URI: ${ZOHO_REDIRECT_URI}|g' docker-compose.yml
fi

