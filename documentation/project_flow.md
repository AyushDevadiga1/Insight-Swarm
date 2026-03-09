# InsightSwarm Live Demo Flow
## (Step-by-Step Script for Tomorrow's Presentation)

---


**Test claims ready to demo:**
1. **Primary (safest):** "Coffee prevents cancer"
2. **Backup (if primary fails):** "Drinking hot water cures COVID-19"
3. **Emergency (quick):** "Earth is flat"

---

## **🎯 DEMO FLOW - OPTION 1: FULL LIVE DEMO (If Internet Works)**

### **TIMING: 3-5 minutes during presentation**

**Best moment to demo:** Right after Slide 10 (Proposed System)

---

### **STEP 1: Transition to Demo (10 seconds)**

**What you say:**
```
"Now, instead of just showing you slides, let me show you 
InsightSwarm in action. This is the actual live system 
deployed on Streamlit Cloud."
```

**What you do:**
- Switch from presentation to browser
- Show the InsightSwarm website
- Make browser fullscreen (F11) so audience can see clearly

**What audience sees:**
```
┌────────────────────────────────────────────┐
│  🐝 InsightSwarm                           │
│  AI-Powered Fact Checker                   │
├────────────────────────────────────────────┤
│                                            │
│  Enter claim to verify:                    │
│  ┌──────────────────────────────────────┐ │
│  │                                      │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  [🔍 Verify Claim]                        │
└────────────────────────────────────────────┘
```

---

### **STEP 2: Set Context (15 seconds)**

**What you say:**
```
"Let's test a common health myth that spreads on WhatsApp. 
I'm going to check: 'Coffee prevents cancer' - something 
many people believe and share."
```

**What you do:**
- Type slowly and clearly so audience can read: **"Coffee prevents cancer"**
- Don't rush - let them see what you're typing

**Pro tip:** 
If nervous, have the claim pre-copied and just paste it. But typing shows it's real-time.

---

### **STEP 3: Click Verify and Narrate (30-45 seconds)**

**What you say while clicking:**
```
"I'll click Verify Claim. Now watch what happens. The 
system is doing several things simultaneously..."
```

**What you do:**
- Click "Verify Claim" button
- **IMMEDIATELY start narrating** - don't wait in silence

**What audience sees (loading screen):**
```
┌────────────────────────────────────────────┐
│  🔄 Verification in Progress...            │
│                                            │
│  ⏳ ProAgent researching...               │
│  ⏳ ConAgent analyzing...                 │
│  ⏳ FactChecker preparing...              │
└────────────────────────────────────────────┘
```

**What you say during the 30-second wait:**
```
"Right now, the system is:

[5 seconds] Fetching sources from Wikipedia and Brave Search 
about coffee and cancer...

[10 seconds] ProAgent is finding all evidence that coffee 
MIGHT help prevent cancer...

[15 seconds] ConAgent is simultaneously finding all evidence 
AGAINST this claim...

[20 seconds] FactChecker is verifying that every source they 
cite actually exists and says what they claim...

[25 seconds] And here we go, the debate is finishing and 
Moderator is making the final decision..."
```

**Pro tip:** 
Keep talking during loading time. Silence is awkward. Narration keeps audience engaged.

---

### **STEP 4: Show Results (30 seconds)**

**What audience sees:**
```
┌────────────────────────────────────────────┐
│  ⚖️ VERDICT: PARTIALLY TRUE                │
│                                            │
│  Confidence: 68% ████████████░░░░░░       │
│                                            │
│  📊 Summary:                               │
│  Coffee is associated with reduced risk of │
│  SOME cancers (liver, colorectal) by       │
│  modest amounts (~15%), but does NOT       │
│  "prevent cancer" as claim states.         │
│                                            │
│  ✅ Verified Sources:                      │
│  • Harvard 2015 Study (pubmed.gov)        │
│  • Cancer.gov Research Summary            │
│  • WHO Nutrition Guidelines               │
│                                            │
│  [📄 View Full Debate Transcript]         │
└────────────────────────────────────────────┘
```

**What you say:**
```
"Perfect! In just 30 seconds, we have our verdict: 
PARTIALLY TRUE with 68% confidence.

[Point to screen] Notice it doesn't just say 'true' or 
'false'. It explains that coffee MAY reduce SOME cancer 
risks by about 15%, but the claim 'prevents cancer' is 
an overstatement.

[Point to sources] And here - see these verified sources? 
The system actually fetched these URLs and confirmed they 
exist and say what our agents claimed. No hallucination."
```

---

### **STEP 5: Show Transparency (30 seconds)**

**What you do:**
- Click "View Full Debate Transcript"

**What audience sees:**
```
┌────────────────────────────────────────────┐
│  💬 DEBATE TRANSCRIPT                      │
├────────────────────────────────────────────┤
│                                            │
│  ✅ ProAgent (12:34:15 PM):               │
│  Coffee contains antioxidants that have    │
│  anti-cancer properties. Harvard 2015      │
│  study shows 15% lower liver cancer risk   │
│  in coffee drinkers.                       │
│  Source: pubmed.gov/study/12345            │
│                                            │
│  ❌ ConAgent (12:34:18 PM):               │
│  ProAgent's claim is misleading. The study │
│  only covers LIVER cancer, not all cancers.│
│  15% reduction is modest, not "prevention."│
│  Some studies link coffee to pancreatic    │
│  cancer in smokers.                        │
│  Source: cancer.gov/research/coffee        │
│                                            │
│  🔬 FactChecker (12:34:22 PM):            │
│  Verification Results:                     │
│  ✓ ProAgent's pubmed.gov source: VERIFIED │
│  ✓ ConAgent's cancer.gov source: VERIFIED │
│  ✗ No hallucinated sources detected       │
│                                            │
│  ⚖️ Moderator (12:34:25 PM):              │
│  Both agents cite valid sources. ProAgent  │
│  is correct that some evidence exists, but │
│  ConAgent correctly notes the claim        │
│  overstates the findings. Verdict:         │
│  PARTIALLY TRUE.                           │
└────────────────────────────────────────────┘
```

**What you say:**
```
"And this is what makes InsightSwarm different. You're not 
just told 'true' or 'false' - you see the entire debate.

[Point to ProAgent] Here's ProAgent finding evidence FOR 
the claim...

[Point to ConAgent] Here's ConAgent challenging that evidence...

[Point to FactChecker] And here's FactChecker verifying that 
both sources are real - no hallucinations.

This transparency means even if you disagree with our verdict, 
you have all the information to judge for yourself."
```

---

### **STEP 6: Quick Second Demo (Optional - if time permits, 45 seconds)**

**What you say:**
```
"Let me show you one more - something completely false this time."
```

**What you do:**
- Go back to main page
- Type: **"Drinking hot water cures COVID-19"**
- Click Verify

**Fast narration during loading:**
```
"This was a viral WhatsApp myth during the pandemic. 
Let's see what happens..."
```

**Expected result:**
```
┌────────────────────────────────────────────┐
│  ⚖️ VERDICT: FALSE                         │
│                                            │
│  Confidence: 95% ████████████████████░    │
│                                            │
│  Summary:                                  │
│  No scientific evidence supports this      │
│  claim. WHO explicitly states no food or   │
│  beverage cures COVID-19.                  │
│                                            │
│  ⚠️ WARNING: Following this advice instead │
│  of proper medical treatment can be        │
│  dangerous.                                │
└────────────────────────────────────────────┘
```

**What you say:**
```
"Perfect. 95% confidence it's FALSE. The system found WHO 
explicitly denying this claim, and even added a warning 
that believing this could be dangerous.

This is how InsightSwarm helps prevent health misinformation 
from spreading."
```

---

### **STEP 7: Return to Presentation (10 seconds)**

**What you say:**
```
"So you've seen it work in real-time. In under a minute, 
we can verify any claim with sources, debate, and 
transparent reasoning. Let me continue with the 
technical architecture..."
```

**What you do:**
- Press Alt+Tab to return to PowerPoint
- Continue from Slide 17 (System Architecture)

-

