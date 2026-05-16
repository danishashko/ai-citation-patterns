"""
_generate_5k_queries.py
========================
Programmatically generate 5,000 unique, category-balanced, May-2026-relevant
search queries for the grounding-citation-analysis pipeline.

Strategy:
  - 25 categories × 200 queries each = 5,000
  - Combine curated topic seeds × intent templates × modifiers
  - Deduplicate, length-filter, save to queries/queries_5k.csv

Output schema matches existing queries.csv:
  query, category, intent, expected_answer_type
"""

import csv
import itertools
import random
import re
from pathlib import Path

random.seed(20260512)  # deterministic

OUT = Path("queries/queries_5k.csv")
TARGET_PER_CAT = 200
TARGET_TOTAL = 5000

# ─────────────────────────────────────────────────────────────────────────────
# Topic seeds per category (curated, real-world)
# ─────────────────────────────────────────────────────────────────────────────

SEEDS = {
    "health": [
        "type 2 diabetes", "high blood pressure", "high cholesterol", "anxiety", "depression",
        "migraines", "insomnia", "thyroid disease", "rheumatoid arthritis", "osteoarthritis",
        "asthma", "COPD", "irritable bowel syndrome", "celiac disease", "Crohn disease",
        "ulcerative colitis", "GERD", "kidney stones", "gallstones", "psoriasis",
        "eczema", "rosacea", "endometriosis", "PCOS", "menopause symptoms",
        "low testosterone", "sleep apnea", "fibromyalgia", "chronic fatigue", "long COVID",
        "Lyme disease", "shingles", "gout", "iron deficiency anemia", "vitamin D deficiency",
        "B12 deficiency", "magnesium deficiency", "low blood sugar", "hyperthyroidism", "hypothyroidism",
        "pneumonia", "bronchitis", "sinusitis", "tonsillitis", "vertigo",
        "tinnitus", "macular degeneration", "glaucoma", "cataracts", "carpal tunnel syndrome",
        "plantar fasciitis", "tennis elbow", "rotator cuff injury", "ACL tear", "concussion",
        "stroke recovery", "heart attack warning signs", "atrial fibrillation", "deep vein thrombosis", "pulmonary embolism",
        "ADHD in adults", "autism in children", "OCD", "PTSD", "bipolar disorder",
        "schizophrenia", "dementia", "Alzheimers disease", "Parkinsons disease", "multiple sclerosis",
        "ALS", "lupus", "Hashimotos thyroiditis", "Addisons disease", "Cushings syndrome",
        "polycystic kidney disease", "irritable bladder", "kidney infection", "appendicitis", "pancreatitis",
        "diverticulitis", "hernia", "varicose veins", "hemorrhoids", "psoriatic arthritis",
        "ankylosing spondylitis", "Ehlers Danlos syndrome", "Marfan syndrome", "MS flare", "diabetic neuropathy",
    ],
    "tech": [
        "Python", "JavaScript", "TypeScript", "Rust", "Go programming language",
        "React", "Vue", "Svelte", "Next.js", "Astro",
        "Node.js", "Deno", "Bun runtime", "FastAPI", "Django",
        "Flask", "Spring Boot", "Express.js", "GraphQL", "REST API",
        "gRPC", "WebSockets", "Server-Sent Events", "WebAssembly", "Service Workers",
        "Docker", "Kubernetes", "Helm", "Terraform", "Ansible",
        "AWS Lambda", "AWS S3", "AWS DynamoDB", "Cloudflare Workers", "Vercel Edge Functions",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
        "ClickHouse", "DuckDB", "SQLite", "Cassandra", "Neo4j",
        "Apache Kafka", "RabbitMQ", "NATS", "MQTT", "ZeroMQ",
        "OAuth 2.0", "OpenID Connect", "JWT", "SAML", "passkeys",
        "TLS 1.3", "HTTPS", "HSTS", "Content Security Policy", "CORS",
        "machine learning", "deep learning", "transformers", "embeddings", "RAG",
        "fine-tuning LLMs", "vector databases", "Pinecone", "Weaviate", "ChromaDB",
        "LangChain", "LlamaIndex", "OpenAI API", "Anthropic Claude API", "Google Gemini API",
        "git rebase", "git cherry-pick", "monorepo", "microservices", "event sourcing",
        "CQRS", "domain driven design", "TDD", "BDD", "pair programming",
        "CI/CD", "GitHub Actions", "GitLab CI", "Jenkins", "ArgoCD",
        "load balancing", "API gateway", "service mesh", "Istio", "Linkerd",
        "Prometheus", "Grafana", "OpenTelemetry", "distributed tracing", "log aggregation",
    ],
    "finance": [
        "401k", "Roth IRA", "traditional IRA", "HSA", "529 plan",
        "index funds", "ETFs", "mutual funds", "individual stocks", "bonds",
        "treasury bonds", "corporate bonds", "municipal bonds", "high yield bonds", "TIPS",
        "dividend investing", "growth investing", "value investing", "REITs", "real estate crowdfunding",
        "robo advisors", "Vanguard", "Fidelity", "Charles Schwab", "Betterment",
        "credit score", "credit utilization", "credit report", "credit freeze", "FICO score",
        "VantageScore", "secured credit card", "balance transfer", "0% APR card", "cashback card",
        "travel rewards card", "personal loan", "auto loan", "mortgage", "refinancing a mortgage",
        "ARM mortgage", "FHA loan", "VA loan", "USDA loan", "jumbo loan",
        "PMI", "home equity loan", "HELOC", "reverse mortgage", "home appraisal",
        "tax brackets", "marginal tax rate", "standard deduction", "itemized deductions", "tax credits",
        "earned income tax credit", "child tax credit", "1099 form", "W2 form", "estimated taxes",
        "self employment tax", "capital gains tax", "wash sale rule", "tax loss harvesting", "Roth conversion",
        "Social Security benefits", "Medicare", "Medicaid", "Medigap", "long term care insurance",
        "term life insurance", "whole life insurance", "umbrella insurance", "renters insurance", "homeowners insurance",
        "stock options", "RSUs", "ESPP", "vesting schedule", "exercise stock options",
        "options trading", "futures trading", "margin trading", "short selling", "covered calls",
        "compound interest", "dollar cost averaging", "rebalancing portfolio", "asset allocation", "Modern Portfolio Theory",
        "CFP", "CFA", "fiduciary advisor", "fee only advisor", "robo advisor",
    ],
    "career": [
        "asking for a raise", "negotiating salary", "negotiating job offer", "performance review", "self evaluation",
        "career change", "switching industries", "going back to school", "MBA", "bootcamps",
        "remote work", "hybrid work", "in-office work", "asynchronous work", "deep work",
        "burnout", "imposter syndrome", "managing up", "managing down", "giving feedback",
        "receiving feedback", "1 on 1 meetings", "skip level meetings", "stand up meetings", "retrospectives",
        "OKRs", "KPIs", "SMART goals", "5 year plan", "career ladder",
        "individual contributor", "first time manager", "engineering manager", "product manager", "data scientist",
        "UX designer", "UI designer", "DevOps engineer", "site reliability engineer", "machine learning engineer",
        "data engineer", "platform engineer", "security engineer", "QA engineer", "technical writer",
        "scrum master", "agile coach", "project manager", "program manager", "chief of staff",
        "LinkedIn profile", "portfolio website", "resume formatting", "cover letter", "thank you note",
        "STAR method interview", "behavioral interview", "technical interview", "system design interview", "case study interview",
        "leetcode practice", "system design practice", "salary negotiation script", "counter offer", "non compete clause",
        "stock options vesting", "RSUs vesting", "PTO policy", "parental leave", "sabbatical leave",
        "remote work taxes", "freelancing", "consulting", "starting an LLC", "personal branding",
        "networking events", "informational interviews", "mentorship", "sponsorship at work", "employee resource groups",
        "diversity equity inclusion", "psychological safety", "team culture", "company values", "mission statement",
        "layoff package", "severance pay", "unemployment benefits", "COBRA insurance", "career coach",
    ],
    "fitness": [
        "5x5 strength training", "starting strength program", "stronglifts", "PPL split", "upper lower split",
        "full body workout", "kettlebell training", "dumbbell only workout", "bodyweight workout", "calisthenics",
        "marathon training", "half marathon training", "couch to 5k", "10k training", "ultramarathon training",
        "HIIT workouts", "tabata training", "metcon workouts", "CrossFit", "F45 training",
        "yoga for beginners", "vinyasa yoga", "ashtanga yoga", "yin yoga", "restorative yoga",
        "pilates", "barre workouts", "zumba", "spin class", "indoor cycling",
        "swimming workouts", "open water swimming", "triathlon training", "Iron Man training", "duathlon training",
        "rowing workouts", "Concept2 erg training", "Olympic lifting", "powerlifting", "strongman training",
        "macros for fat loss", "macros for muscle gain", "protein intake", "carb cycling", "intermittent fasting",
        "creatine supplementation", "pre workout supplements", "BCAAs", "whey protein", "casein protein",
        "rest days", "active recovery", "deload week", "sleep for athletes", "stretching routine",
        "mobility work", "foam rolling", "myofascial release", "dynamic warm up", "cool down stretches",
        "running form", "cadence", "heart rate zones", "VO2 max", "lactate threshold",
        "deadlift form", "squat form", "bench press form", "overhead press form", "pull up progression",
        "muscle up progression", "handstand progression", "front lever progression", "planche progression", "human flag progression",
        "training to failure", "RPE scale", "RIR scale", "periodization", "linear progression",
        "concurrent training", "block periodization", "undulating periodization", "tapering for race", "peaking for meet",
        "knee pain from running", "shin splints", "IT band syndrome", "plantar fasciitis treatment", "tennis elbow rehab",
        "shoulder impingement rehab", "lower back pain exercises", "sciatica relief", "frozen shoulder", "rotator cuff exercises",
    ],
    "food": [
        "sourdough bread", "no knead bread", "focaccia", "pizza dough", "bagels at home",
        "homemade pasta", "fresh ravioli", "gnocchi", "risotto", "paella",
        "Thai green curry", "Thai red curry", "Indian butter chicken", "tikka masala", "biryani",
        "Japanese ramen", "Japanese curry", "sushi at home", "tempura", "miso soup",
        "Korean bibimbap", "Korean BBQ", "kimchi", "kimchi jjigae", "tteokbokki",
        "Mexican carnitas", "barbacoa", "elote", "chiles rellenos", "tamales",
        "French onion soup", "boeuf bourguignon", "coq au vin", "ratatouille", "quiche lorraine",
        "Italian ragu bolognese", "carbonara", "amatriciana", "cacio e pepe", "tiramisu",
        "Greek moussaka", "spanakopita", "tzatziki", "souvlaki", "baklava",
        "smoked brisket", "pulled pork", "ribs in the oven", "sous vide steak", "reverse sear ribeye",
        "perfect roast chicken", "spatchcock turkey", "deep fried turkey", "Thanksgiving stuffing", "cranberry sauce",
        "homemade pie crust", "apple pie", "pumpkin pie", "key lime pie", "pecan pie",
        "chocolate chip cookies", "snickerdoodles", "shortbread cookies", "macarons", "madeleines",
        "sourdough starter", "sourdough discard recipes", "fermented hot sauce", "homemade yogurt", "homemade kefir",
        "kombucha at home", "ginger bug", "water kefir", "sauerkraut", "lacto fermented pickles",
        "pressure canning", "water bath canning", "preserving tomatoes", "freezer meals", "meal prep ideas",
        "low carb meals", "keto meals", "Mediterranean diet meals", "Whole30 meals", "vegan meals",
        "vegetarian meals", "high protein meals", "low FODMAP meals", "anti inflammatory meals", "diabetic friendly meals",
        "knife skills", "mise en place", "deglazing", "braising", "confit",
    ],
    "travel": [
        "Italy itinerary", "France itinerary", "Spain itinerary", "Portugal itinerary", "Greece itinerary",
        "UK itinerary", "Ireland itinerary", "Iceland itinerary", "Norway itinerary", "Sweden itinerary",
        "Japan itinerary", "South Korea itinerary", "Vietnam itinerary", "Thailand itinerary", "Indonesia itinerary",
        "Australia itinerary", "New Zealand itinerary", "Costa Rica itinerary", "Mexico itinerary", "Peru itinerary",
        "Argentina itinerary", "Chile itinerary", "Brazil itinerary", "Colombia itinerary", "Ecuador itinerary",
        "Morocco itinerary", "Egypt itinerary", "Kenya safari", "Tanzania safari", "South Africa itinerary",
        "Tokyo neighborhoods", "Kyoto temples", "Osaka food", "Paris arrondissements", "Rome attractions",
        "London neighborhoods", "Amsterdam canals", "Berlin neighborhoods", "Barcelona neighborhoods", "Lisbon neighborhoods",
        "Bali villages", "Seoul districts", "Bangkok neighborhoods", "Singapore districts", "Hong Kong districts",
        "Buenos Aires neighborhoods", "CDMX neighborhoods", "NYC neighborhoods", "Miami beaches", "Chicago neighborhoods",
        "carry on packing list", "checked bag essentials", "minimalist travel", "digital nomad gear", "long flight comfort",
        "jet lag remedies", "sleep on planes", "travel insurance comparison", "global entry vs TSA precheck", "Clear membership",
        "travel credit cards", "Chase Sapphire Reserve", "Amex Platinum", "Capital One Venture X", "airline credit cards",
        "Star Alliance", "OneWorld alliance", "SkyTeam alliance", "credit card points", "transfer partners",
        "travel hacking", "award flights", "miles vs cash", "airline status match", "hotel status match",
        "Airbnb tips", "Vrbo vs Airbnb", "boutique hotels", "luxury hotels", "hostel etiquette",
        "Eurail pass", "JR Pass Japan", "Renfe Spain trains", "Trenitalia trains", "TGV France",
        "renting a car abroad", "international driving permit", "Schengen visa", "ETIAS", "tourist visa requirements",
        "passport renewal", "second passport", "travel safety solo", "anti theft bag", "hotel room safety",
        "altitude sickness", "Montezuma revenge", "travel vaccines", "malaria prophylaxis", "yellow fever vaccine",
    ],
    "legal": [
        "estate planning", "writing a will", "living will", "healthcare proxy", "power of attorney",
        "revocable trust", "irrevocable trust", "probate process", "intestate succession", "executor duties",
        "small claims court", "filing a lawsuit", "responding to a lawsuit", "default judgment", "garnishment",
        "tenant rights", "landlord obligations", "security deposit dispute", "eviction process", "lease agreement",
        "employment at will", "wrongful termination", "EEOC complaint", "FMLA leave", "ADA accommodation",
        "non disclosure agreement", "non compete clause", "non solicitation agreement", "severance agreement", "release of claims",
        "trademark registration", "patent application", "provisional patent", "copyright registration", "DMCA takedown",
        "LLC formation", "corporation formation", "S corp election", "operating agreement", "bylaws",
        "personal injury claim", "slip and fall claim", "auto accident claim", "medical malpractice", "product liability",
        "divorce process", "uncontested divorce", "child custody", "child support", "alimony",
        "prenuptial agreement", "postnuptial agreement", "domestic partnership", "common law marriage", "annulment",
        "criminal record expungement", "DUI charge", "misdemeanor vs felony", "plea bargain", "jury duty",
        "Miranda rights", "search warrant requirements", "Fourth Amendment", "Fifth Amendment", "self incrimination",
        "small business formation", "sole proprietorship", "partnership agreement", "registered agent", "EIN application",
        "contract formation", "breach of contract", "force majeure clause", "indemnification clause", "limitation of liability",
        "bankruptcy chapter 7", "bankruptcy chapter 13", "bankruptcy chapter 11", "debt settlement", "credit counseling",
        "social security disability", "SSI vs SSDI", "disability appeal", "veterans benefits", "VA disability rating",
        "immigration green card", "H1B visa", "L1 visa", "EB1 visa", "naturalization process",
        "asylum application", "DACA", "TPS", "deportation defense", "immigration appeals",
        "GDPR compliance", "CCPA compliance", "HIPAA compliance", "COPPA compliance", "data breach notification",
    ],
    "education": [
        "Common Core math", "phonics instruction", "Montessori method", "Waldorf education", "Reggio Emilia approach",
        "homeschooling", "unschooling", "world schooling", "charter schools", "private schools",
        "AP courses", "IB program", "dual enrollment", "early college", "gap year",
        "SAT prep", "ACT prep", "LSAT prep", "GRE prep", "GMAT prep",
        "MCAT prep", "USMLE step 1", "USMLE step 2", "bar exam", "CPA exam",
        "college essay", "personal statement", "Common App", "Coalition App", "FAFSA",
        "CSS Profile", "merit scholarships", "need based aid", "work study", "student loans",
        "Pell Grant", "subsidized vs unsubsidized loans", "PLUS loans", "private student loans", "loan refinancing",
        "PSLF", "income driven repayment", "loan forgiveness", "default on student loans", "rehabilitating student loans",
        "study techniques", "active recall", "spaced repetition", "Anki flashcards", "Pomodoro technique",
        "speed reading", "note taking methods", "Cornell notes", "mind mapping", "concept mapping",
        "Bloom taxonomy", "growth mindset", "fixed mindset", "metacognition", "self regulated learning",
        "STEM education", "STEAM education", "computational thinking", "coding for kids", "Scratch programming",
        "early literacy", "reading levels", "Lexile measure", "Fountas Pinnell", "Guided Reading levels",
        "differentiated instruction", "Universal Design for Learning", "IEP", "504 plan", "RTI tiers",
        "ESL instruction", "ELL students", "bilingual education", "dual language immersion", "TESOL",
        "Praxis exam", "teaching license", "alternative certification", "Teach for America", "TFA",
        "online learning", "asynchronous learning", "synchronous learning", "blended learning", "flipped classroom",
        "MOOC platforms", "Coursera", "edX", "Udacity nanodegrees", "Khan Academy",
        "lifelong learning", "professional development", "PMI certification", "AWS certifications", "CompTIA certifications",
    ],
    "science": [
        "general relativity", "special relativity", "quantum entanglement", "wave particle duality", "Heisenberg uncertainty",
        "Standard Model particle physics", "Higgs boson", "dark matter", "dark energy", "black holes",
        "neutron stars", "pulsars", "white dwarfs", "supernovae", "gamma ray bursts",
        "exoplanets", "habitable zone", "Drake equation", "Fermi paradox", "SETI",
        "James Webb Space Telescope", "Hubble Space Telescope", "Mars rovers", "Voyager missions", "Cassini mission",
        "DNA replication", "transcription and translation", "CRISPR Cas9", "gene editing ethics", "GMO crops",
        "stem cells", "induced pluripotent stem cells", "organ regeneration", "tissue engineering", "synthetic biology",
        "mRNA vaccines", "monoclonal antibodies", "antibiotic resistance", "phage therapy", "microbiome research",
        "climate change", "greenhouse effect", "carbon cycle", "ocean acidification", "sea level rise",
        "El Nino", "La Nina", "polar vortex", "atmospheric rivers", "hurricane formation",
        "plate tectonics", "earthquakes", "volcanoes", "geothermal energy", "rare earth minerals",
        "evolution by natural selection", "speciation", "convergent evolution", "punctuated equilibrium", "Cambrian explosion",
        "extinction events", "Permian Triassic extinction", "Cretaceous Paleogene extinction", "Anthropocene", "biodiversity loss",
        "neuroplasticity", "default mode network", "consciousness theories", "global workspace theory", "integrated information theory",
        "psychedelic research", "ketamine therapy", "MDMA assisted therapy", "psilocybin therapy", "DMT effects",
        "fusion energy", "ITER reactor", "tokamak", "stellarator", "inertial confinement fusion",
        "renewable energy", "solar panel efficiency", "wind turbine technology", "battery storage", "grid stability",
        "quantum computing", "quantum supremacy", "Shor algorithm", "Grover algorithm", "quantum error correction",
        "artificial general intelligence", "transformer architecture", "attention mechanism", "diffusion models", "reinforcement learning",
        "protein folding", "AlphaFold", "drug discovery", "molecular dynamics", "computational chemistry",
    ],
    "psychology": [
        "cognitive behavioral therapy", "dialectical behavior therapy", "acceptance and commitment therapy", "EMDR", "exposure therapy",
        "cognitive distortions", "all or nothing thinking", "catastrophizing", "magnification minimization", "personalization",
        "anxiety disorders", "panic disorder", "social anxiety", "generalized anxiety", "agoraphobia",
        "depression treatment", "major depressive disorder", "persistent depressive disorder", "seasonal affective disorder", "postpartum depression",
        "bipolar 1 vs bipolar 2", "rapid cycling", "mixed episode", "hypomania", "psychotic features",
        "OCD compulsions", "intrusive thoughts", "scrupulosity OCD", "harm OCD", "contamination OCD",
        "PTSD symptoms", "complex PTSD", "moral injury", "vicarious trauma", "trauma bonding",
        "attachment styles", "secure attachment", "anxious attachment", "avoidant attachment", "disorganized attachment",
        "narcissistic personality disorder", "borderline personality disorder", "antisocial personality disorder", "histrionic personality disorder", "schizoid personality disorder",
        "ADHD in adults", "ADHD in children", "executive dysfunction", "rejection sensitive dysphoria", "hyperfocus",
        "autism spectrum", "Asperger syndrome", "stimming behaviors", "sensory processing", "masking in autism",
        "Big Five personality", "openness to experience", "conscientiousness", "extraversion", "agreeableness",
        "Myers Briggs", "MBTI types", "Enneagram types", "DISC assessment", "StrengthsFinder",
        "stages of grief", "Kubler Ross model", "complicated grief", "anticipatory grief", "disenfranchised grief",
        "boundaries in relationships", "codependency", "people pleasing", "fawn response", "emotional regulation",
        "polyvagal theory", "autonomic nervous system", "fight flight freeze fawn", "window of tolerance", "co regulation",
        "mindfulness meditation", "loving kindness meditation", "transcendental meditation", "Vipassana meditation", "Zen meditation",
        "self compassion", "growth mindset", "grit", "flow state", "intrinsic motivation",
        "imposter syndrome", "perfectionism", "procrastination", "decision fatigue", "analysis paralysis",
        "social proof", "anchoring bias", "confirmation bias", "Dunning Kruger effect", "loss aversion",
    ],
    "politics": [
        "US electoral college", "ranked choice voting", "open primaries", "closed primaries", "caucuses",
        "gerrymandering", "redistricting", "voter ID laws", "voting rights act", "absentee voting",
        "first amendment", "second amendment", "fourth amendment", "fifth amendment", "fourteenth amendment",
        "executive order", "executive privilege", "impeachment process", "filibuster", "cloture",
        "Supreme Court nominations", "judicial review", "stare decisis", "originalism", "living constitution",
        "federalism", "states rights", "10th amendment", "interstate commerce clause", "supremacy clause",
        "checks and balances", "separation of powers", "legislative branch", "executive branch", "judicial branch",
        "campaign finance", "Citizens United", "Super PACs", "501c4 organizations", "dark money",
        "lobbying", "K Street", "revolving door", "regulatory capture", "iron triangle",
        "single payer healthcare", "Medicare for All", "public option", "ACA Obamacare", "Medicaid expansion",
        "minimum wage debate", "universal basic income", "earned income tax credit", "child tax credit", "SNAP benefits",
        "immigration reform", "DACA program", "asylum process", "border security", "comprehensive immigration reform",
        "criminal justice reform", "qualified immunity", "police reform", "bail reform", "mass incarceration",
        "marijuana legalization", "decriminalization vs legalization", "drug scheduling", "harm reduction", "psychedelic policy",
        "climate policy", "Green New Deal", "carbon tax", "cap and trade", "Paris Agreement",
        "trade policy", "NAFTA USMCA", "WTO", "tariffs", "trade deficit",
        "foreign policy", "soft power", "hard power", "smart power", "balance of power",
        "NATO alliance", "UN Security Council", "ICC International Criminal Court", "World Bank", "IMF",
        "EU institutions", "European Parliament", "European Commission", "European Council", "European Court of Justice",
        "Brexit aftermath", "Scottish independence", "Catalonia independence", "Taiwan strait", "Ukraine war",
    ],
    "history": [
        "Roman Empire", "fall of Rome", "Roman Republic", "Punic Wars", "Roman emperors",
        "ancient Greece", "Athenian democracy", "Spartan society", "Peloponnesian War", "Alexander the Great",
        "ancient Egypt", "pharaohs", "pyramids of Giza", "Cleopatra", "Tutankhamun",
        "Mesopotamia", "Sumerians", "Babylonians", "Assyrians", "Code of Hammurabi",
        "Persian Empire", "Cyrus the Great", "Darius the Great", "Xerxes", "Achaemenid Empire",
        "Han dynasty", "Tang dynasty", "Ming dynasty", "Qing dynasty", "Three Kingdoms period",
        "Mongol Empire", "Genghis Khan", "Kublai Khan", "Mongol invasions of Europe", "Pax Mongolica",
        "Byzantine Empire", "Justinian", "Hagia Sophia", "fall of Constantinople", "Eastern Orthodox Schism",
        "Islamic Golden Age", "Caliphate", "Umayyad Caliphate", "Abbasid Caliphate", "Ottoman Empire",
        "Crusades", "First Crusade", "Knights Templar", "Saladin", "Reconquista",
        "feudalism", "Magna Carta", "Black Death", "Hundred Years War", "War of the Roses",
        "Renaissance", "Italian Renaissance", "Northern Renaissance", "Medici family", "Leonardo da Vinci",
        "Reformation", "Martin Luther", "Henry VIII", "Council of Trent", "Counter Reformation",
        "Age of Discovery", "Christopher Columbus", "Ferdinand Magellan", "Vasco da Gama", "Hernan Cortes",
        "Spanish conquest of the Americas", "Aztec Empire", "Inca Empire", "Maya civilization", "Triangle Trade",
        "Enlightenment", "Voltaire", "Rousseau", "American Revolution", "French Revolution",
        "Napoleonic Wars", "Battle of Waterloo", "Congress of Vienna", "Industrial Revolution", "Victorian Era",
        "American Civil War", "Reconstruction era", "Gilded Age", "Progressive Era", "Roaring Twenties",
        "Great Depression", "New Deal", "World War 1", "Treaty of Versailles", "World War 2",
        "Holocaust", "D Day", "Pearl Harbor", "atomic bomb", "Cold War",
        "Berlin Wall", "Cuban Missile Crisis", "Vietnam War", "Civil Rights Movement", "fall of the Soviet Union",
    ],
    "lifestyle": [
        "minimalism", "decluttering", "Marie Kondo method", "Swedish death cleaning", "tiny house living",
        "van life", "off grid living", "homesteading", "permaculture", "urban gardening",
        "indoor plants", "houseplant care", "monstera care", "fiddle leaf fig care", "snake plant care",
        "skincare routine", "Korean skincare", "double cleansing", "retinol", "vitamin C serum",
        "hyaluronic acid", "niacinamide", "AHA BHA exfoliants", "sunscreen SPF", "anti aging skincare",
        "haircare routine", "scalp care", "hair porosity", "low porosity hair", "high porosity hair",
        "curly hair routine", "CGM Curly Girl Method", "co washing", "deep conditioning", "protein treatment",
        "capsule wardrobe", "personal style", "color analysis", "Kibbe body types", "essential clothing items",
        "sustainable fashion", "thrifting tips", "secondhand shopping", "clothing repair", "mending visible",
        "morning routine", "evening routine", "habit stacking", "atomic habits", "tiny habits",
        "journaling", "bullet journal", "gratitude journal", "morning pages", "stream of consciousness writing",
        "meditation routine", "breathwork", "Wim Hof method", "box breathing", "alternate nostril breathing",
        "cold plunge", "ice bath benefits", "sauna benefits", "infrared sauna", "contrast therapy",
        "biohacking", "continuous glucose monitor", "HRV tracking", "Oura ring", "Whoop strap",
        "circadian rhythm", "morning sunlight", "blue light blocking", "sleep hygiene", "sleep tracking",
        "intermittent fasting protocols", "16 8 fasting", "OMAD", "alternate day fasting", "5 2 diet",
        "elimination diet", "Whole30", "AIP autoimmune protocol", "low FODMAP", "GAPS diet",
        "home organization", "pantry organization", "closet organization", "garage organization", "junk drawer organization",
        "self care Sunday", "digital detox", "screen time limits", "dopamine fasting", "device free dinners",
        "hosting tips", "dinner party planning", "wine pairing basics", "cheese board", "charcuterie board",
    ],
    "parenting": [
        "newborn care", "baby sleep training", "Ferber method", "cry it out method", "no cry sleep solution",
        "breastfeeding", "pumping schedule", "bottle feeding", "formula feeding", "combo feeding",
        "starting solids", "baby led weaning", "purees", "BLW vs purees", "first foods",
        "potty training", "Oh Crap potty training", "elimination communication", "bedwetting solutions", "regression after potty training",
        "toddler tantrums", "terrible twos", "threenager", "fournado", "big feelings",
        "gentle parenting", "Montessori parenting", "RIE parenting", "attachment parenting", "free range parenting",
        "screen time toddlers", "screen time preschoolers", "screen time school age", "parental controls", "kid friendly apps",
        "ADHD in kids", "autism diagnosis", "speech delays", "early intervention", "OT for kids",
        "picky eating", "division of responsibility", "Ellyn Satter feeding", "food jags", "introducing new foods",
        "sibling rivalry", "only child concerns", "spacing siblings", "twin parenting", "blended families",
        "co parenting after divorce", "parallel parenting", "custody schedules", "divorce with kids", "talking to kids about divorce",
        "puberty for girls", "puberty for boys", "first period talk", "puberty book recommendations", "talking about sex",
        "social media for tweens", "first phone for kids", "wait until 8th", "smartphone alternatives", "kid safe browsers",
        "back to school routines", "homework help", "test anxiety in kids", "bullying intervention", "cyberbullying",
        "teen anxiety", "teen depression", "self harm warning signs", "eating disorders in teens", "substance use in teens",
        "college prep for high schoolers", "extracurricular balance", "summer programs", "internships for teens", "first job for teens",
        "raising boys today", "raising girls today", "raising LGBTQ kids", "raising bilingual kids", "raising multilingual kids",
        "concerns about anxiety", "play therapy", "child therapy when needed", "family therapy", "parent coaching",
        "preparing for baby 2", "telling toddler about new baby", "regression with new sibling", "sleep with two kids", "managing two under two",
        "child development milestones", "CDC milestones", "ASQ screening", "denver developmental screening", "MCHAT autism screening",
    ],
    "environment": [
        "climate change basics", "global warming evidence", "IPCC reports", "1.5C target", "net zero emissions",
        "carbon footprint", "personal carbon budget", "carbon offsets", "carbon credits", "voluntary carbon market",
        "renewable energy transition", "solar power growth", "wind power growth", "geothermal energy", "tidal energy",
        "battery storage grid", "vehicle to grid", "EV adoption", "EV charging infrastructure", "EV battery recycling",
        "deforestation Amazon", "deforestation Borneo", "boreal forest loss", "reforestation projects", "afforestation",
        "biodiversity loss", "sixth mass extinction", "endangered species", "IUCN red list", "rewilding",
        "ocean plastic pollution", "Great Pacific Garbage Patch", "microplastics in food", "microplastics in body", "microplastics in water",
        "ocean acidification", "coral reef bleaching", "Great Barrier Reef", "kelp forest decline", "marine protected areas",
        "freshwater scarcity", "aquifer depletion", "Colorado River basin", "Lake Mead water level", "California drought",
        "wildfires", "California wildfires", "Canadian wildfires", "wildfire smoke health", "fire ecology",
        "hurricanes climate change", "atmospheric rivers", "polar vortex", "heat waves", "urban heat island",
        "sea level rise", "ice sheet melt", "Greenland ice sheet", "Antarctic ice sheet", "permafrost thaw",
        "methane emissions", "methane leaks", "agricultural methane", "landfill methane", "permafrost methane",
        "regenerative agriculture", "no till farming", "cover crops", "agroforestry", "silvopasture",
        "vertical farming", "hydroponics", "aquaponics", "controlled environment agriculture", "indoor farming",
        "plant based diet impact", "meat consumption climate", "dairy industry emissions", "food waste impact", "circular food systems",
        "fast fashion impact", "textile waste", "clothing recycling", "natural fibers vs synthetic", "leather alternatives",
        "single use plastic ban", "plastic bag ban", "straw ban", "Styrofoam ban", "bottle deposit programs",
        "circular economy", "cradle to cradle design", "product as a service", "right to repair", "extended producer responsibility",
        "ESG investing", "green bonds", "sustainability reporting", "Scope 1 2 3 emissions", "TCFD reporting",
    ],
    "economics": [
        "supply and demand", "price elasticity", "income elasticity", "substitution effect", "income effect",
        "inflation causes", "deflation causes", "stagflation", "hyperinflation", "disinflation",
        "monetary policy", "fiscal policy", "Federal Reserve", "ECB European Central Bank", "Bank of Japan",
        "interest rate hikes", "interest rate cuts", "yield curve", "inverted yield curve", "term premium",
        "GDP growth", "real GDP", "nominal GDP", "GDP deflator", "GDP per capita",
        "unemployment rate", "labor force participation", "U6 underemployment", "structural unemployment", "frictional unemployment",
        "Phillips curve", "NAIRU", "wage price spiral", "labor share of income", "productivity growth",
        "international trade", "comparative advantage", "absolute advantage", "trade balance", "current account",
        "tariffs and trade wars", "non tariff barriers", "anti dumping duties", "safeguards", "WTO disputes",
        "exchange rate regimes", "fixed exchange rate", "floating exchange rate", "currency peg", "currency board",
        "balance of payments", "capital account", "foreign direct investment", "portfolio investment", "remittances",
        "Keynesian economics", "monetarism", "Austrian economics", "MMT modern monetary theory", "supply side economics",
        "neoclassical economics", "behavioral economics", "institutional economics", "evolutionary economics", "ecological economics",
        "income inequality", "wealth inequality", "Gini coefficient", "Lorenz curve", "Palma ratio",
        "Universal Basic Income", "negative income tax", "EITC expansion", "wealth tax", "land value tax",
        "minimum wage effects", "monopsony in labor markets", "right to work laws", "union membership decline", "gig economy growth",
        "housing affordability crisis", "rent control debate", "zoning reform", "missing middle housing", "single family zoning",
        "antitrust enforcement", "monopoly power", "market concentration", "Big Tech antitrust", "FTC merger guidelines",
        "central bank digital currency", "stablecoins", "DeFi protocols", "tokenization of assets", "real world assets RWA",
        "developing economies", "emerging markets", "frontier markets", "BRICS expansion", "global south",
    ],
    "marketing": [
        "SEO basics", "technical SEO", "on page SEO", "off page SEO", "local SEO",
        "keyword research", "long tail keywords", "search intent", "topic clusters", "pillar pages",
        "link building", "guest posting", "broken link building", "skyscraper technique", "HARO link building",
        "Core Web Vitals", "page speed optimization", "mobile first indexing", "schema markup", "structured data",
        "content marketing", "blog content strategy", "evergreen content", "content repurposing", "content distribution",
        "email marketing", "email list building", "lead magnets", "welcome sequence", "abandoned cart emails",
        "newsletter monetization", "Substack vs Beehiiv", "ConvertKit Kit", "Mailchimp", "Klaviyo",
        "social media marketing", "Instagram strategy", "TikTok strategy", "LinkedIn organic strategy", "Twitter X strategy",
        "Pinterest marketing", "YouTube SEO", "YouTube Shorts strategy", "podcast marketing", "podcast launch strategy",
        "Facebook ads", "Google ads", "TikTok ads", "LinkedIn ads", "YouTube ads",
        "retargeting campaigns", "lookalike audiences", "custom audiences", "interest targeting", "behavioral targeting",
        "conversion rate optimization", "A B testing", "multivariate testing", "landing page optimization", "form optimization",
        "marketing funnel", "AIDA model", "pirate metrics AARRR", "growth loops", "PLG product led growth",
        "customer lifetime value", "customer acquisition cost", "LTV CAC ratio", "payback period", "unit economics",
        "brand strategy", "brand positioning", "brand archetypes", "brand voice", "visual identity",
        "rebranding", "logo design", "color theory branding", "typography in branding", "brand storytelling",
        "PR strategy", "media outreach", "journalist relationships", "press releases", "thought leadership",
        "influencer marketing", "creator economy", "affiliate marketing", "UGC user generated content", "ambassador programs",
        "marketing analytics", "GA4 Google Analytics", "attribution modeling", "marketing mix modeling", "incrementality testing",
        "AI in marketing", "ChatGPT for marketers", "AI content generation", "AI image generation", "marketing automation",
    ],
    "business": [
        "starting a business", "business plan", "lean canvas", "business model canvas", "minimum viable product",
        "market validation", "customer discovery", "problem solution fit", "product market fit", "channel market fit",
        "pricing strategy", "value based pricing", "cost plus pricing", "freemium model", "tiered pricing",
        "SaaS metrics", "MRR ARR", "churn rate", "net revenue retention", "gross margin",
        "fundraising basics", "pre seed funding", "seed round", "Series A", "Series B",
        "venture capital", "angel investors", "syndicates", "SAFE notes", "convertible notes",
        "bootstrapping", "indie hacking", "solopreneurship", "calm company", "lifestyle business",
        "team building", "first hires", "hiring process", "founder market fit", "co founder agreements",
        "equity splits", "vesting schedule", "founder vesting", "advisor equity", "ESOP setup",
        "term sheets", "valuation methods", "DCF valuation", "comparable company analysis", "precedent transactions",
        "due diligence", "data room", "cap table management", "409a valuation", "stock option grants",
        "growth strategy", "land and expand", "PLG product led growth", "SLG sales led growth", "channel partnerships",
        "sales process", "BANT qualification", "MEDDIC sales", "SPIN selling", "challenger sale",
        "outbound sales", "inbound sales", "account based marketing", "sales enablement", "RevOps",
        "customer success", "customer health score", "QBR quarterly business review", "expansion revenue", "renewal management",
        "operations management", "supply chain", "vendor management", "procurement", "inventory management",
        "financial planning", "FP A", "burn rate", "runway calculation", "cash flow forecasting",
        "exit strategies", "acquisition", "IPO process", "SPAC", "secondary sale",
        "international expansion", "EOR employer of record", "PEO", "transfer pricing", "VAT compliance",
        "AI in business", "AI strategy", "AI ROI", "AI workforce transformation", "AI governance",
    ],
    "ai_research": [
        "transformer architecture", "self attention mechanism", "multi head attention", "positional encoding", "layer normalization",
        "BERT model", "GPT architecture", "Llama models", "Gemini models", "Claude models",
        "RAG retrieval augmented generation", "prompt engineering", "few shot learning", "zero shot learning", "chain of thought",
        "RLHF reinforcement learning from human feedback", "RLAIF", "DPO direct preference optimization", "constitutional AI", "Anthropic principles",
        "fine tuning models", "LoRA adapters", "QLoRA", "PEFT", "instruction tuning",
        "embeddings", "sentence embeddings", "cross encoder", "bi encoder", "ColBERT",
        "vector databases", "Pinecone", "Weaviate", "Qdrant", "Milvus",
        "agent frameworks", "LangChain", "LlamaIndex", "AutoGen", "CrewAI",
        "tool use in LLMs", "function calling", "MCP model context protocol", "OpenAI function calling", "Anthropic tool use",
        "AI hallucinations", "factuality in LLMs", "grounding in LLMs", "RAG evaluation", "needle in haystack",
        "context window", "long context attention", "Flash Attention", "Ring Attention", "sliding window attention",
        "mixture of experts", "MoE architecture", "Mixtral", "Switch Transformer", "expert routing",
        "diffusion models", "stable diffusion", "DALL E 3", "Midjourney", "Imagen 3",
        "text to video", "Sora", "Runway Gen 3", "Veo Google", "Pika labs",
        "speech models", "Whisper", "ElevenLabs voices", "voice cloning", "TTS text to speech",
        "AI safety", "alignment research", "interpretability", "mechanistic interpretability", "scalable oversight",
        "AI governance", "EU AI Act", "Biden executive order AI", "AI export controls", "AI risk frameworks",
        "AGI definition", "AGI timeline predictions", "superintelligence", "AI takeoff scenarios", "compute scaling laws",
        "evaluation benchmarks", "MMLU", "HumanEval", "GPQA", "ARC AGI",
        "AI startups 2026", "model providers comparison", "open source vs closed source models", "model serving infrastructure", "vLLM",
    ],
    "geo_strategy": [
        "answer engine optimization", "AEO", "GEO generative engine optimization", "LLM SEO", "AI search optimization",
        "Google AI Mode optimization", "Gemini app optimization", "ChatGPT search optimization", "Perplexity optimization", "Bing Copilot optimization",
        "schema markup for AI", "FAQ schema", "HowTo schema", "Article schema", "Product schema",
        "structured content for AI", "extractable content", "chunked content", "semantic HTML for AI", "ARIA for AI",
        "first party data strategy", "zero party data", "consent based data", "privacy in AI search", "GDPR for AI search",
        "topical authority", "entity SEO", "knowledge graph optimization", "Wikidata listing", "Wikipedia citations",
        "brand mentions for AI", "co citations", "implicit links", "brand SERP", "knowledge panel optimization",
        "citation worthy content", "primary source content", "expert author E E A T", "first hand experience content", "original research SEO",
        "AI Overviews ranking factors", "Featured Snippets optimization", "People Also Ask optimization", "Knowledge Graph entries", "Image Pack optimization",
        "competitive AI tracking", "share of voice in AI", "brand visibility in LLMs", "AI mention monitoring", "LLM perception audits",
        "log file analysis for AI bots", "GPTBot crawler", "Google Extended", "ClaudeBot", "PerplexityBot",
        "robots.txt for AI bots", "blocking AI crawlers", "allowing AI crawlers strategically", "llms.txt standard", "AI scraping policy",
        "content licensing to LLMs", "OpenAI publisher partnerships", "Reddit data licensing", "Stack Overflow API restrictions", "Quora content licensing",
        "answer engine ranking factors", "freshness for AI search", "authority signals for AI", "EEAT for AI search", "user signals for AI search",
        "AI Mode SERP layout", "Gemini UI changes", "ChatGPT search UI", "Perplexity UI", "Copilot UI",
        "tracking AI Mode citations", "tracking Gemini citations", "tracking ChatGPT citations", "tracking Perplexity citations", "monitoring brand in LLMs",
        "ChatGPT plugins replaced by GPTs", "OpenAI Apps", "ChatGPT Actions", "Perplexity Pages", "Gemini Gems",
        "voice search and AI", "smart speaker optimization", "Google Assistant", "Alexa skills", "Siri",
        "image search and AI", "Google Lens optimization", "visual search SEO", "multimodal search", "Pinterest visual search",
        "video and AI search", "YouTube AI summaries", "podcast transcript SEO", "video chapter optimization", "Whisper transcription SEO",
    ],
    "law_firm_marketing": [
        "personal injury lawyer SEO", "criminal defense lawyer SEO", "family law SEO", "divorce lawyer SEO", "estate planning lawyer SEO",
        "law firm Google Business Profile", "law firm reviews strategy", "law firm citations", "Avvo profile optimization", "Justia profile",
        "legal directory backlinks", "FindLaw listings", "Martindale Hubbell listings", "Lawyers.com profile", "Super Lawyers listings",
        "law firm content marketing", "FAQ pages for law firms", "practice area pages", "city specific landing pages", "near me legal queries",
        "law firm conversion optimization", "click to call buttons", "intake forms optimization", "live chat for law firms", "after hours intake",
        "law firm Google Ads", "personal injury PPC", "criminal defense PPC", "family law PPC", "DUI defense PPC",
        "law firm Local Service Ads", "LSA legal", "Google Screened lawyers", "law firm display advertising", "law firm retargeting",
        "law firm Facebook ads", "law firm LinkedIn ads", "law firm YouTube ads", "law firm video marketing", "lawyer testimonials video",
        "lawyer thought leadership", "lawyer LinkedIn strategy", "lawyer Twitter strategy", "lawyer podcast strategy", "lawyer book authoring",
        "law firm reputation management", "Avvo rating improvement", "negative review removal", "ARAG defense", "online review responses",
        "law firm CRM", "Clio Grow", "Lawmatics", "MyCase intake", "Smokeball intake",
        "case acquisition cost", "legal lead conversion rates", "lawyer signed case rates", "case value vs marketing spend", "law firm ROI tracking",
        "ethical advertising rules", "ABA Model Rules", "state bar advertising rules", "no win no fee marketing", "settlement amount disclaimers",
        "lawyer SEO link building", "scholarship link building lawyers", "guest posting on legal blogs", "HARO for lawyers", "legal industry awards",
        "lawyer YouTube channel", "lawyer TikTok marketing", "lawyer Instagram marketing", "lawyer Threads strategy", "lawyer Mastodon strategy",
        "law firm answer engine optimization", "lawyer AI Mode visibility", "lawyer Gemini visibility", "lawyer ChatGPT recommendations", "lawyer Perplexity citations",
        "law firm blog posting frequency", "law firm content audit", "law firm content refresh", "law firm topical authority", "law firm pillar content",
        "personal injury answer optimization", "DUI answer optimization", "child custody answer optimization", "estate planning answer optimization", "bankruptcy answer optimization",
        "lawyer schema markup", "Attorney schema", "LegalService schema", "FAQPage for lawyers", "HowTo for lawyers",
        "law firm site speed", "law firm Core Web Vitals", "law firm mobile optimization", "law firm accessibility WCAG", "law firm site security",
    ],
    "ecommerce": [
        "Shopify store setup", "Shopify themes", "Shopify Plus features", "WooCommerce vs Shopify", "BigCommerce vs Shopify",
        "Shopify apps must have", "Shopify checkout extensibility", "Shopify Markets", "Shopify Translate Adapt", "Shopify B2B",
        "product photography", "lifestyle product photos", "white background product photos", "video product showcase", "360 product photography",
        "product page optimization", "PDP best practices", "size guide implementation", "product reviews on PDP", "user generated content on PDP",
        "Klaviyo email flows", "abandoned cart flow", "browse abandonment flow", "post purchase flow", "winback flow",
        "SMS marketing ecommerce", "Postscript SMS", "Attentive SMS", "Klaviyo SMS", "compliance for SMS",
        "Meta Ads ecommerce", "iOS 14 impact ads", "first party data for ads", "Conversions API", "Google Enhanced Conversions",
        "TikTok Shop", "Instagram Shopping", "Pinterest Shopping", "YouTube Shopping", "Snapchat Shopping",
        "Amazon FBA", "Amazon Seller Central", "Amazon PPC", "Amazon SEO", "Amazon brand registry",
        "Walmart marketplace", "Target Plus marketplace", "Etsy SEO", "eBay listings", "Mercari listings",
        "headless commerce", "composable commerce", "MACH architecture", "JAMstack ecommerce", "Hydrogen Shopify",
        "ecommerce CRO", "site search optimization", "filter and facet optimization", "category page optimization", "internal linking ecommerce",
        "shipping strategy", "free shipping threshold", "carbon neutral shipping", "international shipping", "DDP delivered duty paid",
        "returns management", "Loop Returns", "Happy Returns", "ReturnLogic", "return policy optimization",
        "subscription commerce", "Recharge subscriptions", "Skio subscriptions", "Stay AI subscriptions", "Bold Subscriptions",
        "loyalty programs", "Smile.io", "Yotpo loyalty", "Stamped loyalty", "Recharge loyalty",
        "wholesale and B2B ecommerce", "Faire wholesale", "wholesale on Shopify", "B2B pricing tiers", "net terms",
        "ecommerce analytics", "GA4 ecommerce", "Shopify Analytics", "Triple Whale", "Northbeam attribution",
        "post purchase surveys", "Fairing surveys", "Enquire Labs", "KnoCommerce", "Octane AI",
        "AI in ecommerce", "AI product descriptions", "AI image generation for ecom", "AI personalization", "AI search and discovery",
    ],
    "real_estate": [
        "first time home buyer", "FHA loan requirements", "VA loan requirements", "conventional loan", "jumbo loan",
        "mortgage preapproval", "mortgage underwriting", "mortgage closing process", "earnest money deposit", "appraisal contingency",
        "home inspection checklist", "radon testing", "mold inspection", "sewer scope inspection", "termite inspection",
        "buyer agent commission", "seller agent commission", "exclusive buyer agency", "dual agency disclosure", "NAR settlement impact",
        "seller disclosures", "as is sale", "sight unseen offer", "escalation clause", "love letter to seller",
        "closing costs breakdown", "title insurance", "owners title vs lenders title", "escrow account", "prorated property taxes",
        "HOA basics", "HOA fees", "HOA reserve study", "special assessments", "HOA board meeting",
        "condo vs townhouse vs single family", "patio home", "manufactured home", "mobile home", "modular home",
        "selling a house FSBO", "MLS listing", "professional staging", "open house strategy", "virtual home tour",
        "house flipping basics", "ARV after repair value", "70% rule house flipping", "BRRRR strategy", "wholesaling real estate",
        "rental property analysis", "1% rule rentals", "cap rate", "cash on cash return", "DSCR loan",
        "1031 exchange", "delayed exchange", "reverse 1031 exchange", "qualified intermediary", "boot in 1031",
        "DST Delaware Statutory Trust", "REIT investing", "private REIT", "publicly traded REIT", "non traded REIT",
        "real estate syndications", "limited partner LP", "general partner GP", "preferred return", "promote structure",
        "self storage investing", "mobile home park investing", "ATM business investing", "land investing", "raw land deals",
        "Airbnb investing", "short term rental regulations", "STR data tools", "AirDNA", "Rabbu",
        "house hacking", "duplex house hacking", "ADU strategy", "rent by the room", "live in flip",
        "real estate seller financing", "subject to mortgage", "lease option", "wraparound mortgage", "land contract",
        "tax benefits of real estate", "depreciation real estate", "cost segregation study", "real estate professional status", "passive activity loss rules",
        "real estate forecast 2026", "housing inventory levels", "mortgage rates outlook", "homebuilder sentiment", "housing affordability index",
    ],
    "saas": [
        "SaaS pricing pages", "good better best pricing", "value metric pricing", "usage based pricing", "seat based pricing",
        "trial vs freemium", "reverse trial", "self serve onboarding", "product led growth", "sales led growth",
        "PQL product qualified lead", "MQL marketing qualified lead", "SQL sales qualified lead", "lead scoring", "lead routing",
        "SaaS landing page", "above the fold copy", "social proof on landing pages", "customer logos", "testimonial design",
        "SaaS demo video", "product walkthrough", "interactive demos", "Navattic", "Reprise demos",
        "SaaS onboarding emails", "activation email sequence", "feature announcement emails", "win back emails", "upgrade nudge emails",
        "in app onboarding", "Userpilot", "Appcues", "Pendo", "WalkMe",
        "SaaS analytics", "Mixpanel funnels", "Amplitude analytics", "Heap analytics", "PostHog",
        "SaaS metrics dashboard", "ARR growth", "logo retention", "net dollar retention", "rule of 40",
        "SaaS churn analysis", "voluntary churn", "involuntary churn", "dunning emails", "Stripe Smart Retries",
        "SaaS pricing experiments", "value based pricing research", "willingness to pay surveys", "Van Westendorp pricing", "Gabor Granger method",
        "SaaS segmentation", "ICP ideal customer profile", "buyer persona", "use case segmentation", "industry vertical segmentation",
        "SaaS positioning", "April Dunford positioning", "category creation", "category design", "blue ocean strategy",
        "SaaS competitive intelligence", "competitor pricing analysis", "feature comparison pages", "alternatives pages SEO", "vs pages SEO",
        "SaaS partnerships", "tech partnerships", "channel partnerships", "OEM partnerships", "embed partnerships",
        "SaaS integrations strategy", "Zapier integration", "Make integration", "n8n integration", "native integrations",
        "SaaS API monetization", "API rate limits", "API key management", "developer relations", "API documentation tools",
        "SaaS enterprise sales", "RFP responses", "security questionnaires", "SOC 2 compliance", "ISO 27001 certification",
        "SaaS expansion playbook", "land and expand", "multi product expansion", "geographic expansion", "vertical expansion",
        "SaaS exit", "strategic acquisition", "private equity acquisition", "going public IPO", "secondary tender",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Templates by intent
# ─────────────────────────────────────────────────────────────────────────────

# Each template: (template_string, intent, expected_answer_type)
TEMPLATES = [
    # explanations
    ("what is {x}", "informational", "explanation"),
    ("what is {x} and how does it work", "informational", "explanation"),
    ("how does {x} work", "informational", "explanation"),
    ("how does {x} actually work", "informational", "explanation"),
    ("what causes {x}", "informational", "explanation"),
    ("why does {x} matter in 2026", "informational", "explanation"),
    ("what is the science behind {x}", "informational", "explanation"),
    ("explain {x} in simple terms", "informational", "explanation"),
    ("what does {x} mean", "informational", "explanation"),
    ("history of {x}", "informational", "explanation"),
    # lists
    ("best {x} in 2026", "informational", "list"),
    ("top 10 {x}", "informational", "list"),
    ("most common {x}", "informational", "list"),
    ("benefits of {x}", "informational", "list"),
    ("disadvantages of {x}", "informational", "list"),
    ("pros and cons of {x}", "informational", "list"),
    ("types of {x}", "informational", "list"),
    ("examples of {x}", "informational", "list"),
    ("symptoms of {x}", "informational", "list"),
    ("warning signs of {x}", "informational", "list"),
    ("alternatives to {x}", "informational", "list"),
    # comparisons
    ("{x} vs alternatives", "informational", "comparison"),
    ("difference between {x} and similar options", "informational", "comparison"),
    ("is {x} worth it", "transactional", "comparison"),
    # how-to
    ("how to start with {x}", "instructional", "steps"),
    ("how to learn {x} fast", "instructional", "steps"),
    ("how to choose {x}", "instructional", "steps"),
    ("how to improve {x}", "instructional", "steps"),
    ("how to fix {x}", "instructional", "steps"),
    ("how to avoid {x}", "instructional", "steps"),
    ("step by step guide to {x}", "instructional", "steps"),
    ("how to set up {x}", "instructional", "steps"),
    ("how long does {x} take", "informational", "estimate"),
    ("how much does {x} cost in 2026", "informational", "estimate"),
    # research / newsy
    ("latest research on {x}", "informational", "explanation"),
    ("{x} in 2026", "informational", "explanation"),
    ("future of {x}", "informational", "explanation"),
    ("trends in {x} 2026", "informational", "list"),
    ("recent advances in {x}", "informational", "list"),
    # recommendations
    ("recommended {x} for beginners", "informational", "list"),
    ("expert tips for {x}", "informational", "list"),
    # safety / risk
    ("is {x} safe", "informational", "explanation"),
    ("risks of {x}", "informational", "list"),
    ("side effects of {x}", "informational", "list"),
]

# Specialised intent buckets — narrow templates per category
NARROW_TEMPLATES = {
    "health":        [("symptoms of {x}", "informational", "list"),
                       ("treatment options for {x}", "informational", "list"),
                       ("how to manage {x} naturally", "instructional", "steps"),
                       ("complications of untreated {x}", "informational", "list")],
    "finance":       [("how does {x} work", "informational", "explanation"),
                       ("is {x} a good investment in 2026", "transactional", "explanation"),
                       ("tax implications of {x}", "informational", "explanation"),
                       ("how to maximize {x}", "instructional", "steps")],
    "career":        [("how to negotiate {x}", "instructional", "steps"),
                       ("what skills are needed for {x}", "informational", "list"),
                       ("career path for {x}", "informational", "explanation")],
    "tech":          [("when to use {x}", "informational", "explanation"),
                       ("performance considerations for {x}", "informational", "list"),
                       ("alternatives to {x} in 2026", "informational", "list"),
                       ("security best practices for {x}", "informational", "list")],
    "fitness":       [("training plan for {x}", "instructional", "steps"),
                       ("recovery from {x}", "instructional", "steps"),
                       ("common mistakes in {x}", "informational", "list")],
    "food":          [("how to make {x} at home", "instructional", "steps"),
                       ("what to serve with {x}", "informational", "list"),
                       ("storage tips for {x}", "informational", "list")],
    "travel":        [("best time to visit {x}", "informational", "estimate"),
                       ("budget for {x} trip", "informational", "estimate"),
                       ("must see places in {x}", "informational", "list")],
    "legal":         [("how to file for {x}", "instructional", "steps"),
                       ("rights regarding {x}", "informational", "list"),
                       ("statute of limitations for {x}", "informational", "explanation")],
    "education":     [("study plan for {x}", "instructional", "steps"),
                       ("test prep tips for {x}", "instructional", "steps")],
    "science":       [("recent breakthroughs in {x}", "informational", "list"),
                       ("controversies around {x}", "informational", "list")],
    "psychology":    [("how to cope with {x}", "instructional", "steps"),
                       ("therapist recommendations for {x}", "informational", "list")],
    "politics":      [("recent debate around {x}", "informational", "explanation"),
                       ("policy proposals for {x}", "informational", "list")],
    "history":       [("causes of {x}", "informational", "list"),
                       ("legacy of {x}", "informational", "explanation"),
                       ("key figures in {x}", "informational", "list")],
    "lifestyle":     [("daily routine for {x}", "instructional", "steps"),
                       ("budget friendly {x}", "informational", "list")],
    "parenting":     [("age appropriate approach to {x}", "informational", "explanation"),
                       ("how to talk to kids about {x}", "instructional", "steps")],
    "environment":   [("how individuals can help with {x}", "instructional", "steps"),
                       ("policies addressing {x}", "informational", "list")],
    "economics":     [("indicators related to {x}", "informational", "list"),
                       ("historical context for {x}", "informational", "explanation")],
    "marketing":     [("KPIs for {x}", "informational", "list"),
                       ("agency vs in house for {x}", "informational", "comparison")],
    "business":      [("playbook for {x}", "instructional", "steps"),
                       ("benchmarks for {x}", "informational", "list")],
    "ai_research":   [("how does {x} compare to GPT 4o", "informational", "comparison"),
                       ("benchmarks for {x}", "informational", "list"),
                       ("limitations of {x}", "informational", "list")],
    "geo_strategy":  [("how to optimize for {x}", "instructional", "steps"),
                       ("metrics for {x}", "informational", "list")],
    "law_firm_marketing": [("ROI of {x}", "informational", "estimate"),
                            ("getting started with {x}", "instructional", "steps")],
    "ecommerce":     [("conversion rate benchmarks for {x}", "informational", "estimate"),
                       ("ROI of {x}", "informational", "estimate")],
    "real_estate":   [("market outlook for {x}", "informational", "explanation"),
                       ("financing options for {x}", "informational", "list")],
    "saas":          [("benchmarks for {x}", "informational", "list"),
                       ("playbook for {x}", "instructional", "steps")],
}


def _normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", q).strip().lower()
    q = q.replace(" .", ".").replace(" ,", ",")
    return q


def generate_for_category(category: str, seeds: list[str], target: int) -> list[dict]:
    """Generate `target` unique queries for a category by combining seeds and templates."""
    out: list[dict] = []
    seen: set[str] = set()

    pool = TEMPLATES + NARROW_TEMPLATES.get(category, [])
    # First pass: every template × every seed (Cartesian)
    combos = list(itertools.product(seeds, pool))
    random.shuffle(combos)

    for seed, (tpl, intent, ans_type) in combos:
        q = _normalize_query(tpl.format(x=seed))
        if not (4 <= len(q.split()) <= 14):  # 4–14 word range, sane query length
            continue
        if q in seen:
            continue
        seen.add(q)
        out.append({"query": q, "category": category, "intent": intent, "expected_answer_type": ans_type})
        if len(out) >= target:
            break

    return out


def main():
    queries: list[dict] = []
    global_seen: set[str] = set()

    for cat, seeds in SEEDS.items():
        cat_queries = generate_for_category(cat, seeds, TARGET_PER_CAT)
        # filter against global dupes
        unique_cat = []
        for q in cat_queries:
            if q["query"] not in global_seen:
                global_seen.add(q["query"])
                unique_cat.append(q)
        # If we lost some to global dedupe, top up by relaxing: try more combos
        if len(unique_cat) < TARGET_PER_CAT:
            extra_needed = TARGET_PER_CAT - len(unique_cat)
            extras = generate_for_category(cat, seeds, TARGET_PER_CAT * 3)
            for q in extras:
                if q["query"] in global_seen:
                    continue
                global_seen.add(q["query"])
                unique_cat.append(q)
                if len(unique_cat) >= TARGET_PER_CAT:
                    break
        queries.extend(unique_cat[:TARGET_PER_CAT])

    # Trim or pad to TARGET_TOTAL
    if len(queries) > TARGET_TOTAL:
        random.shuffle(queries)
        queries = queries[:TARGET_TOTAL]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query", "category", "intent", "expected_answer_type"])
        w.writeheader()
        w.writerows(queries)

    # Stats
    by_cat: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    for q in queries:
        by_cat[q["category"]] = by_cat.get(q["category"], 0) + 1
        by_intent[q["intent"]] = by_intent.get(q["intent"], 0) + 1

    print(f"\nGenerated {len(queries)} unique queries → {OUT}")
    print("\nBy category:")
    for c, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {c:<22} {n}")
    print("\nBy intent:")
    for i, n in sorted(by_intent.items(), key=lambda kv: -kv[1]):
        print(f"  {i:<18} {n}")


if __name__ == "__main__":
    main()
