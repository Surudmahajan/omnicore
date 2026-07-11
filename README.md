<img width="4320" height="1440" alt="hh26 main poster 2 with sponsors 3x1 (4320 x 1440 px) (2)" src="https://github.com/user-attachments/assets/c698b2cd-da84-4cb0-9276-125c6a7244aa" />

# 🚀 OmniCore

> Developer Data Infrastructure Platform. Automatically discover, download, clean, normalize, version, and expose high-quality datasets through a unified API ecosystem.

---

## 📌 Problem & Domain

Whenever developers, data engineers, or AI researchers need high-quality data to build applications or train machine learning models, it is an absolute nightmare. They are forced to manually scrape messy websites, download gigabytes of dirty CSV files, write custom parsers for every single format, and figure out where to host the data on their own servers. This massive overhead leads to "Data Fragmentation," where developers waste weeks just trying to get their data ready before they even write a single line of application code. 

OmniCore permanently fixes data fragmentation by providing a central, standardized, and highly performant API infrastructure for curated, production-ready datasets. We do the heavy lifting of gathering and cleaning the data so you can focus on building.

**Themes Selected:**
- [x] Human Experience & Productivity  
- [ ] Climate & Sustainability Systems  
- [ ] HealthTech & Bio Platforms  
- [ ] Learning & Knowledge Systems  
- [ ] Work, Finance & Digital Economy  
- [ ] Infrastructure, Mobility & Smart Systems  
- [ ] Trust, Identity & Security  
- [ ] Media, Social & Interactive Platforms  
- [ ] Public Systems, Governance and Civic Tech  
- [x] Developer Tools & Software Infrastructure  

---

## 🎯 Objective

OmniCore solves the massive pain point of data fragmentation and infrastructure overhead for software engineers, data scientists, and AI builders. 

- **The target users:** Frontend and backend developers, AI engineers, Data Scientists, and researchers who need immediate access to structured data.
- **The pain point:** Finding, cleaning, formatting, indexing, and hosting reliable data takes weeks of manual, repetitive labor. Data often rots or becomes outdated.
- **The value your solution provides:** A single, centralized API key grants instant access to a massive, curated, and fully normalized registry of production-ready datasets. Whether you need healthcare statistics, global geographical data, or sports analytics, you can query it effortlessly without managing any backend databases yourself.

### How OmniCore Augments & Enhances User Experience:
- **Instant Flow State:** By removing the friction of data gathering, developers can stay entirely in their "flow state." They think of an idea and can begin implementing it immediately, drastically accelerating time-to-market.
- **Unified Consistency:** Because every dataset on OmniCore passes through our standardization engine, the user experience is incredibly consistent. A developer querying financial data uses the exact same pagination, sorting, and filtering structure as a developer querying sports data. No more learning ten different APIs.
- **AI-Guided Discovery:** The BuildPilot AI radically enhances the user experience by acting as a personal data architect. Instead of manually searching for what data might work for a project, users simply describe their idea in natural language, and the AI curates the perfect datasets and provides the exact code needed to integrate them.

---

## 🧠 Team & Approach

### Team Name:  
`CodeCatalyst`

### Team Members:  
- Surud  
- Shravani 
- Shankilya
- Snehal

### Your Approach:
- **Why we chose this problem:** We personally experienced the severe frustration of spending more time finding, cleaning, and formatting datasets than actually building the core features of our applications during hackathons and personal projects. We knew there had to be a better way to provide "data-as-a-service."
- **Key challenges we addressed:** Handling and serving massive data payloads gracefully without crashing the client's browser (which we solved via strict, optimized API pagination and server-side filtering) and deploying a seamless, unified full-stack monolith architecture so our frontend and backend could share the exact same domain space effortlessly.
- **Breakthroughs:** Integrating "BuildPilot", an advanced AI engine powered by large language models that analyzes a developer's raw project idea, understands the context, and instantly recommends the perfect datasets alongside customized starter code. It bridges the gap between imagination and execution.

---

## 🛠️ Tech Stack

### Core Technologies Used:
- **Frontend:** React.js, Custom Vanilla CSS (Premium Glassmorphism design system)
- **Backend:** Python FastAPI (High-performance async framework)
- **Database:** PostgreSQL (Serverless, highly scalable architecture via Neon.tech)
- **APIs:** Hugging Face Datasets API (for remote sync), OpenRouter AI (for LLM inference)
- **Hosting:** Render.com (Monolithic Full-stack Docker deployment)

### Additional Technologies Used:
- [x] AI / ML  
- [ ] Web3 / Blockchain  
- [ ] Cyber Security 
- [x] Cloud  

---

## ✨ Key Features

- ✅ **Data Explorer:** A beautiful, intuitive UI registry of production-ready datasets spanning multiple domains, complete with domain filtering and quality scores.
- ✅ **API Console:** Instantly query datasets with just 3 lines of code using secure Bearer token authentication, robust pagination, and dynamic search parameters.
- ✅ **BuildPilot AI:** Describe your app idea in plain English, and the AI generates a comprehensive Project Blueprint with recommended datasets, system architecture, and ready-to-copy code snippets.
- ✅ **Solution Packs:** Curated, pre-packaged bundles of datasets (e.g., "Healthcare Analytics Pack" or "Location Intelligence Pack") designed specifically for common startup and project types.

---

## 📽️ Demo & Deliverables

- **Demo Video Link:** https://www.youtube.com/watch?v=CcX74pM7mKk  
- **Deployment Link:** https://omnicoreapi.onrender.com/  
- **Pitch Deck / PPT:** https://docs.google.com/presentation/d/1k9hRmF5PYDjuakDDoY9-CxIm775J-XopxZ6ooEGPqcc/

---

## ✅ Tasks & Bonus Checklist

- [x] All team members completed the mandatory social task  
- [x] Bonus Task 1 – Badge sharing  
- [ ] Bonus Task 2 – Blog/article  

---

## 🧪 How to Run the Project

### Requirements:
- Python 3.11+
- Node.js & npm
- PostgreSQL database URL (Neon.tech)
- Hugging Face / OpenRouter API Keys

### Local Setup:
```bash
# 1. Clone the repository
git clone https://github.com/Surudmahajan/omnicore.git
cd omnicore/backend

# 2. Set up Backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
# (Create a .env file with DATABASE_URL, JWT_SECRET, OPENROUTER_API_KEY)
uvicorn main:app --reload

# 3. Set up Frontend (In a new terminal)
cd ../frontend
npm install
npm start
```

---

## 🧬 Future Scope

While our cloud-deployed API is incredibly powerful, our ultimate vision for OmniCore is to empower developers with **complete data sovereignty and localized speed**. 

- 🖥️ **Locally Run Software & Desktop Client:** We plan to package OmniCore as a native desktop application (using Electron or Tauri) and a localized Docker container. This will allow developers to run the entire data infrastructure on their own local machines, entirely offline. 
- ⚡ **Zero-Latency Local Queries:** By running OmniCore locally, developers will experience absolute zero-latency API responses. Local machine learning models and applications can query the local OmniCore instance millions of times per second without worrying about internet connectivity, rate limits, or bandwidth costs.
- 🔒 **Total Privacy and Air-Gapping:** For enterprises and developers working on highly sensitive projects, a locally run OmniCore means no data ever leaves their network. They can sync the datasets they need once, disconnect from the internet, and build in a completely air-gapped environment.
- 📈 **More integrations:** Expand background sync to Kaggle, direct GitHub CSV scraping, and automated web-crawling datasets.
- 🌐 **Webhooks:** Allow developers to subscribe to webhooks to automatically trigger rebuilds of their apps when the underlying datasets they rely on get updated in real-time.

---

## 📎 Resources / Credits

- Hugging Face for dataset hosting, registry, and retrieval infrastructure.
- Neon.tech for lightning-fast serverless PostgreSQL database capabilities.
- Llama-3 (via OpenRouter) for powering the BuildPilot AI intelligence.
- React and FastAPI communities for the incredible open-source frameworks.

---

## 🏁 Final Words

Building OmniCore was an incredibly challenging but rewarding journey. Merging a robust React frontend with a high-performance Python backend into a single, seamless deployable monolith on Render taught us so much about modern software architecture, Dockerization, and API security. We faced numerous hurdles, especially around handling massive data payloads efficiently, but overcoming them made our platform incredibly resilient. We are deeply proud of what we've built, and we are absolutely thrilled to present OmniCore to the world!

---
