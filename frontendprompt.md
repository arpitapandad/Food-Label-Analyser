> **Role & Objective:**
> Act as an expert UI/UX designer and front-end web developer. Create a sleek, modern, mobile-first web application (optimised specifically for smartphone viewports, e.g., 375px–430px width, centred on desktop screens with a clean frame if viewed on larger devices). The website’s purpose is to verify front-of-pack nutritional claims on packaged foods by allowing users to scan both the **ingredient list** and the **nutritional value table** using their phone's camera.
> **Visual Aesthetic & Colour Palette:**
> * **Theme:** Sleek, trustworthy, health-tech aesthetic with subtle glassmorphism, rounded corners (`16px`–`24px`), soft drop shadows, and crisp typography (use Google Fonts like `Plus Jakarta Sans` or `Inter`).
> * **Colour Scheme:** A smooth, modern gradient blend of **warm amber/yellow, crisp white, and vibrant coral/red**—evoking food packaging, nutrition traffic-light alerts, and modern wellness apps. Use white (`#FFFFFF`) as the primary clean surface for cards and inputs, soft warm yellow (`#FFFBEB` to `#FDE68A`) for background washes and highlights, and energetic red/coral (`#EF4444` to `#DC2626`) for primary CTAs, scan triggers, and alert badges.
> 
> 
> **Layout Structure (Based on Wireframe):**
> 1. **Top Navigation Bar:**
> * **Left:** A clean hamburger menu icon (opens a sleek slide-out drawer with navigation links like *Home, How It Works, About the Research*).
> * **Right:** Two compact, pill-shaped utility buttons/icons (e.g., *Scan History* and *Help/Guide*).
> 
> 
> 2. **Hero Section:**
> * Bold, engaging headline: *"How true are claims made on the front of packaged foods? Try it out!"*
> * Subtle subtext explaining that users can verify marketing claims (like "High Protein", "No Added Sugar", or "Heart Healthy") against actual back-of-pack facts.
> 
> 
> 3. **Interactive Verification Card (Core Feature):**
> * **Step 1 – Claim Input:** A prominent, labelled text input field titled **"Enter claim to check"** with helpful placeholder text (e.g., *"e.g., 100% Whole Wheat, Zero Trans Fat..."*) and quick-select suggestion chips below it.
> * **Step 2 – Dual Scan Action:** A section titled **"Scan the ingredient list and nutritional label"**. Design this as an interactive two-step mobile camera trigger (using HTML5 `<input type="file" accept="image/*" capture="environment">`) so the user clearly sees two distinct scan slots or a sequential two-scan progress state:
> 1. *Scan 1: Ingredient List* (shows camera icon, status indicator: Pending/Captured, and thumbnail preview).
> 2. *Scan 2: Nutritional Value Table* (shows camera icon, status indicator: Pending/Captured, and thumbnail preview).
> 
> 
> * **Verify CTA Button:** A bold, gradient red-to-yellow primary action button (*"Verify Claim"*) that becomes active once the claim and both scans are provided, displaying a sleek mock results card showing a "True / Misleading / False" verdict badge and breakdown.
> 
> 
> 4. **Research Callout Section:**
> * Positioned cleanly above the footer, include a distinct secondary CTA button styled with a subtle gradient border or soft fill labelled **"Read my survey paper"** (opens a modal preview or links to the research paper).
> 
> 
> 5. **Footer:**
> * A grounded, minimal footer containing project information, a brief disclaimer about nutritional data verification, and quick links.
> 
> 
> 
> 
> **Technical Requirements:**
> * Build using semantic HTML5, modern CSS (Tailwind CSS or clean custom CSS with CSS variables), and vanilla JavaScript for interactive states (hamburger drawer toggle, camera/file upload previews for both scans, simulated scan-to-result flow, and survey paper modal).
> * Ensure large, thumb-friendly touch targets (minimum `48px` height) suitable for one-handed phone usage.
> 
> 

---
