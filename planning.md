# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This function will take the description, (Optional) the size, and (Optional) the maximum price from the users query and filter the listings.json for the input params. It will then sort the found listings by relevance to the parsed query values. Finally, it will return a list of dictionaries corresponding to the relevant listings found.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): The brief or full description of the clothing item the user is looking for.
- `size` (str | None): The optional parameter for the user's size.
- `max_price` (float | None): The optional parameter for the threshold price of a listing.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
The function will return a list of dictionaries. The dictionaries are sorted by relevancy in most to least order.
To ensure our data retains schema, the happy path for the function will return:
- list[dict]

Each dictionary item contains:
- `id` (str)
- `title` (str)
- `description` (str)
- `category` (str)
- `style_tags` (list[str])
- `size` (str)
- `condition` (str)
- `price` (float)
- `colors` (list[str])
- `brand` (str | None)
- `platform` (str)

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
If this function fails, it should exit early and return the contracted structure of:
- results = []

The orchestrator agent will recognize this result by checking if results are empty storing a helpful message in session['error'], stop the workflow before calling suggest_outfit, and call the LLM for a response to the user.
---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool will take in a `new_item` from the relevancy list and the user's wardrobe which may be empty. The function will prompt an LLM with these inputs as context and a dedicated system prompt which instructs the LLM to create one or two outfits from the context.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A dictionary representing the item selected from `listings`.
- `wardrobe` (dict | None): The wardrobe schema dictionary that represents the user's current clothing items. 

**What it returns:**
<!-- Describe the return value -->
The function will return a result from the LLM model which describes one or two suggested outfits as a tuple of strings.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
- If no wardrobe is given to the function, the function should set session['error'] to a string containing a helpful message for the agent and return early.
- If no outfit can be suggested, the function should set session['error'] to describe the error and return early.

The agent will then check for these edge cases before continuing to call create_fit_card. If the cases are present, the agent will make a final call to the LLM with the context and errors to return a useful response to the user.
---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): ...
- `new_item` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     Use ASCII art or a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html).
     Do NOT embed an image — graders need to read your diagram directly in the file;
     an embedded image or screenshot cannot be evaluated.
     You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:**
<!-- Continue until the full interaction is complete -->

**Final output to user:**
<!-- What does the user actually see at the end? -->
