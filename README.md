# 🏰 Lieand's Moon Castle — Living Lore Discord World

A Discord-powered **AI-driven fantasy world simulator** where server activity becomes evolving mythology.  
Powered by **Groq LLMs + Discord.py + Streamlit dashboard**.

---

## 🌍 Overview

Lieand's Moon Castle transforms a Discord server into a **living fantasy realm**:

- 🏰 Channels become territories (capital, battlefield, cursed zones)
- 👑 Users are assigned factions automatically
- ⚔️ Messages can trigger wars and conflicts
- 💰 Activity generates faction influence (economy system)
- 📜 Groq turns events into mythological lore entries
- 📩 A selected user receives private “royal chronicle” updates via DM
- 🧠 Streamlit dashboard visualizes the entire world

---

## ⚙️ Features

### 🏰 World System
- Each Discord server has its own isolated world
- Persistent faction, player, and lore storage

### 👑 Factions
- The Council  
- The Lurkers  
- The They Gang  
- The Randos  

Users are auto-assigned and balanced across factions.

---

### 🗺️ Territories
Channels act as regions:

| Channel | Region Name | Type |
|----------|------------|------|
| `#general` | Capital of Nullreach | Capital |
| `#war` | Bloodfields | Battlefield |
| `#void` | Cursed Expanse | Cursed |

---

### 💰 Economy System
- Every message grants **influence points**
- Longer messages = more influence
- Factions grow dynamically over time

---

### ⚔️ War System
Detects keywords like:

- attack  
- raid  
- invade  
- declare war  
- battle  

Triggers:
- war events
- AI-generated battle lore
- faction conflict escalation

---

### 📜 AI Lore Engine (Groq)
Uses `llama-3.3-70b-versatile` to:
- Convert chat activity into historical chronicles
- Expand conflicts into full wars
- Write immersive fantasy storytelling

---

### 📩 Royal Chronicle (DM System)
A selected user receives:
- All lore updates
- Server-wide historical events
- War summaries

Acts as the “Royal Observer of the Moon Castle”.

---

### 📊 Streamlit Dashboard
Live visualization of:

- Faction influence
- Player distribution
- Recent lore entries
- World state history

---

## 🧱 Project Structure
