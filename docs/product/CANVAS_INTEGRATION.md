# Canvas LMS Integration: ChatGPT & Plagiarism Detection (LTI 1.3)

This guide documents the integration of **IntegrityDesk** as a **Plagiarism Detection Platform (PDP)** within Canvas, focusing on our **ChatGPT Detection** "killer feature."

---

## 1. The ChatGPT Detection "Killer Feature"

IntegrityDesk uses a dual-tier approach to detect AI-generated code (GPT-4, Claude 3, etc.) with **90%+ accuracy**:

-   **CodeBERT Zero-Shot Classifier**: Analyzes the latent semantic structure of the code, detecting patterns unique to LLM generation (optimal logic flow, predictable token distributions).
-   **Stylometric Contrast**: Compares the submission's style (variable naming, comment habits, structural entropy) against a human-written baseline. AI code is typically "too consistent" and adheres to perfect PEP8/style-guide patterns that students often deviate from.

In Canvas, this appears as a **"Similarity & AI Probability" flag** directly in the SpeedGrader.

---

## 2. Plagiarism Detection Platform (PDP) Setup

Unlike standard LTI tools, the PDP integration allows Canvas to automatically send student submissions to IntegrityDesk for forensic analysis.

### 2.1 Developer Key Configuration
1.  **Account Admin** > **Developer Keys** > **+ LTI Key**.
2.  **Redirect URIs**: `https://your-domain.com/api/v1/lti/launch`
3.  **OIDC Initiation Url**: `https://your-domain.com/api/v1/lti/login`
4.  **LTI Advantage Services**:
    *   Enable **Plagiarism Detection Platform** (PDP).
    *   Enable **Assignment Grade Services** (AGS).
5.  **Plagiarism Detection Platform Callback**:
    *   Set the **Originality Report URL** to `https://your-domain.com/api/v1/lti/pdp/callback/{submission_id}`.

---

## 3. Deep Linking (Content Selection)

IntegrityDesk supports **Deep Linking**, allowing instructors to enable "Forensic Mode" for specific assignments directly within the Canvas assignment settings.

-   **Message Type**: `LtiDeepLinkingRequest`.
-   **Workflow**: When an instructor creates an assignment and selects IntegrityDesk as the external tool, they are presented with a "Content Selection" screen to enable specific forensic tiers (e.g., "Full AI Detection" or "Basic Structural Matching").

---

## 4. Grading & Evidence Review

1.  **SpeedGrader Integration**: When a teacher opens a student submission in Canvas SpeedGrader, they will see an IntegrityDesk icon.
2.  **Originality Report**: Clicking the icon opens the **Forensic Evidence Report** directly within a Canvas iframe, displaying:
    *   **AI Probability (e.g., 94% AI-Generated)**.
    *   **Similarity Heatmap**.
    *   **Side-by-Side Signed PDF Evidence**.
3.  **Grade Sync**: Forensic risk levels are automatically synchronized with the Canvas Gradebook.

---
**IntegrityDesk Enterprise Support**
*Zero-Shot AI Detection. Seamless LMS Integration.*
