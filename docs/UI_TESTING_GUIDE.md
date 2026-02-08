# Football Chatbot - UI Testing Guide

This guide provides test scenarios for verifying the chatbot UI functionality. Each section includes prompts to send and expected responses.

**NEW: Hybrid LLM Responses** - All responses now use the pipeline for accurate data, then the LLM formats it into natural, conversational language. Responses should be grounded in real numbers but read naturally.

---

## Setup

1. Start the backend API:
   ```cmd
   set DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/football_analytics
   uvicorn api.main:app --reload
   ```

2. Start the frontend:
   ```cmd
   cd frontend
   npm run dev
   ```

3. Open http://localhost:5173 in your browser

---

## Test 1: Basic Team Profile

**Prompt:** `Tell me about the Chiefs`

**Expected Response (LLM-formatted, grounded in data):**
```
The Chiefs have been one of the most efficient offenses in the league this season. 
They're averaging +0.058 EPA per play, which puts them well above average. 

What stands out is their passing game - they're throwing on about 61% of plays with 
a pass EPA of +0.088, meaning they're generating nearly a tenth of a point above 
expectation on every pass play.

Defensively they've been solid too, holding opponents to -0.142 EPA per play - 
that's a pretty stingy defense.
```

**Verify:**
- ✅ Numbers match the actual data (check `data` in response)
- ✅ Response is conversational, not bullet points
- ✅ `used_llm: true` in response
- ✅ Pipeline shows "team_profile"

---

## Test 2: Team Comparison

**Prompt:** `Chiefs vs 49ers`

**Expected Response (LLM-formatted):**
```
This is a matchup of two offensive powerhouses, but the 49ers have the edge this season.

San Francisco is putting up +0.166 EPA per play compared to KC's +0.058 - that's a 
significant gap of about 0.11 points per play. The 49ers are doing it with a more 
balanced attack too, passing on 55% of plays versus KC's 61%.

Both teams can move the ball, but if these numbers hold, SF would have the advantage 
in a shootout.
```

**Verify:**
- ✅ Both teams' stats are accurately stated
- ✅ Comparison is objective, not biased
- ✅ Natural language explanation

---

## Test 3: Situation Analysis (Run vs Pass)

**Prompt:** `Should I run or pass on 3rd and 5 at the 40?`

**Expected Response:**
```
**3rd & 5**
At the 40 yard line

**Expected Points Added:**
• Pass: +0.XXX
• Run: +0.XXX

**Recommendation: [PASS/RUN]** (XX% confidence)
[Play type] has X.XXX higher expected value.
```

**Verify:**
- ✅ Down, distance, yardline are correct (3, 5, 40)
- ✅ EPA values for both play types
- ✅ Clear recommendation

---

## Test 3b: Situation with Defensive Formation

**Prompt:** `Should I run or pass on 2nd and 5 at the 30 with 8 in the box?`

**Expected Response:**
```
**2nd & 5**
At the 30 yard line
Defense showing 8 in the box

**Expected Points Added:**
• Pass: +0.XXX (boosted due to stacked box)
• Run: +0.XXX

**Recommendation: PASS** (XX% confidence)

**Defensive Read:** Stacked box (8 defenders) favors the pass
```

**Verify:**
- ✅ Defenders in box extracted (8)
- ✅ Defensive insight shown
- ✅ Recommendation accounts for box count

**Other defensive formation queries to test:**
- `3rd and 2 with a light box` → Should favor run
- `1st and 10 with 6 men in the box` → Should note favorable run conditions

---

## Test 4: 4th Down Decision

**Prompt:** `Should I go for it on 4th and 2 at the 35?`

**Expected Response:**
```
**4th & 2 at the 35**
(52 yard field goal)

**Go For It:**
• Expected Points: X.XX
• TD Probability: X.X%
• Turnover Risk: XX.X%

**Kick Field Goal:**
• Expected Points: X.XX
• Success Rate: XX.X%

**Punt:**
• Expected Points: X.XX
```

**Verify:**
- ✅ All three options shown
- ✅ Field goal distance calculated (100 - 35 - 17 = 48... wait, should be ~52)
- ✅ Clear recommendation

---

## Test 5: Player Rankings

**Prompt:** `Top 5 running backs by EPA`

**Expected Response:**
```
**Top RBs by Epa Per Play**

1. **[Player Name]** (TEAM)
   EPA: +0.XXX (XX attempts, XX% shrinkage)
2. **[Player Name]** (TEAM)
   EPA: +0.XXX (XX attempts, XX% shrinkage)
...
```

**Verify:**
- ✅ Player names (not IDs like "00-0033873")
- ✅ Team abbreviations
- ✅ EPA values and attempt counts

---

## Test 6: Team Tendencies

**Prompt:** `How often do the Ravens pass?`

**Expected Response:**
```
**BAL Tendencies**

**Overall:**
• Pass Rate: 57.6%
• Shotgun Rate: 84.8%
• Passes 3.7% less than league average
```

**Verify:**
- ✅ Team correctly identified as BAL
- ✅ Pass rate and other tendencies shown

---

## Test 7: Natural Language Variations

Test that these all work:

| Prompt | Expected Pipeline |
|--------|-------------------|
| `KC stats` | team_profile |
| `How good are the Eagles?` | team_profile |
| `Compare Chiefs and Bills` | team_comparison |
| `Who's better Chiefs or Bills?` | team_comparison |
| `Chiefs and 49ers` | team_comparison |
| `run or pass 2nd and 8` | situation_epa |
| `best quarterbacks` | player_rankings |
| `top 10 WRs` | player_rankings |

---

## Test 8: Follow-Up Questions (Conversation History)

This tests the conversation history feature. **Send these in sequence:**

### Conversation Flow 1: Team Follow-ups

1. **First:** `Tell me about the Chiefs`
   - Expected: KC profile

2. **Follow-up:** `What about the Bills?`
   - Expected: BUF profile (same analysis type, different team)

3. **Follow-up:** `Compare them to the Ravens`
   - Expected: BUF vs BAL comparison (uses last team as team1)

### Conversation Flow 2: Situation Follow-ups

1. **First:** `Should I run or pass on 3rd and 5 at the 40?`
   - Expected: Situation analysis at 40 yard line

2. **Follow-up:** `What about at the 20?`
   - Expected: Same 3rd and 5, but at 20 yard line

### Conversation Flow 3: Position Follow-ups

1. **First:** `Top 5 running backs`
   - Expected: RB rankings

2. **Follow-up:** `What about quarterbacks?`
   - Expected: QB rankings

---

## Test 9: Yardline Parsing Edge Cases

| Prompt | Expected Yardline |
|--------|-------------------|
| `run or pass 3rd and 5 at my 36` | 36 |
| `2nd and 8 at the 40 yard line` | 40 |
| `3rd and 7 from the 25` | 25 |
| `1st and 10 at midfield` | 50 |
| `3rd and 2 on their 15` | 15 |
| `4th and 1 at my own 28` | 72 (100-28) |
| `4th and goal from the 1` | 1 |

---

## Test 10: Error Handling

### Missing Information

**Prompt:** `run or pass`

**Expected:** Error message asking for down and distance
```
I couldn't complete that analysis: Down and distance required
```

### Invalid Team

**Prompt:** `Tell me about the Unicorns`

**Expected:** Graceful handling or general query fallback

---

## Test 11: User Context (Favorite Team)

1. Set favorite team in Settings panel to "KC"
2. Send: `How does my team compare to the Bills?`
3. **Expected:** KC vs BUF comparison (uses favorite team)

---

## Test 12: Dark Mode

1. Toggle dark mode in the UI
2. Verify all text is readable
3. Verify charts/visualizations adapt to dark theme

---

## Test 13: Quick Actions

Click each quick action button and verify:

| Button | Expected Query |
|--------|----------------|
| "Run or Pass?" | Opens situation query template |
| "Team Profile" | Opens team query template |
| "Compare Teams" | Opens comparison template |
| "4th Down" | Opens decision analysis template |

---

## Test 14: Mobile Responsiveness

1. Open browser DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select mobile device (iPhone, Pixel)
4. Verify:
   - ✅ Chat input is accessible
   - ✅ Messages don't overflow
   - ✅ Settings panel is usable
   - ✅ Quick actions wrap properly

---

## Test 15: EPA Chart Visualization

For situation analysis queries, verify the EPA chart appears:

1. Send: `run or pass 2nd and 5 at the 30`
2. Check for visual EPA comparison chart below the text response
3. Verify bars show correct relative heights

---

## Test 16: Raw Data Toggle

1. Send any query
2. Click "Show raw data" below the response
3. Verify JSON data is displayed
4. Click "Hide raw data" to collapse

---

## Common Issues & Troubleshooting

### "Connection refused" error
- Backend API not running
- Fix: `uvicorn api.main:app --reload`

### "Database connection failed"
- PostgreSQL not running or wrong credentials
- Fix: Check DATABASE_URL and restart API

### Player names showing as IDs
- Database missing player names
- Fix: Re-run data ingestion or check player_season_stats table

### Follow-ups not working
- Need to use same session
- Fix: Don't clear chat between messages; check session_id is being sent

---

## Performance Benchmarks

| Operation | Expected Time |
|-----------|---------------|
| Team profile | < 500ms |
| Team comparison | < 700ms |
| Situation analysis | < 300ms |
| Player rankings | < 1s |
| 4th down simulation | < 2s |

---

## Automated E2E Tests

Run the automated test suite to verify all pipelines:

```cmd
python tests/e2e/run_e2e_tests.py
```

Expected: 32/34 tests pass (2 intentional failures for vague queries)

---

## Test 3: Situation Analysis (Hybrid Response)

**Prompt:** `Should I run or pass on 3rd and 5 at the 40?`

**Expected Response (LLM-formatted):**
```
On 3rd and 5 at the 40, the numbers slightly favor passing.

Pass plays in this situation average +0.145 EPA while runs come in at +0.111. 
That's about a 0.034 point edge for passing - not huge, but meaningful over time.

I'd lean pass here, though with only 57% confidence. The defense can't really 
sell out against either option at this distance.
```

**Verify:**
- ✅ Down/distance/yardline correctly identified
- ✅ EPA values match the `data` object
- ✅ Recommendation explained naturally

---

## Test 3b: Situation with Defensive Formation

**Prompt:** `Should I run or pass on 2nd and 5 at the 30 with 8 in the box?`

**Expected Response (LLM-formatted):**
```
With 8 in the box, the defense is clearly expecting run - and the numbers say 
you should make them pay for it.

At 2nd and 5 from the 30, pass EPA jumps to around +0.18 when you factor in 
the stacked box, while run EPA drops to about +0.08. That's over a tenth of a 
point difference.

Take the shot downfield. They're giving you single coverage on the outside.
```

**Verify:**
- ✅ Defensive formation acknowledged
- ✅ Strategic implication explained
- ✅ Numbers adjusted for box count

---

## Validating LLM Grounding

Every response should be grounded in actual data. To verify:

1. **Check the `data` field** in the response JSON
2. **Compare numbers** - LLM response should use the exact EPA values from data
3. **Run validation tests:**
   ```cmd
   python tests/validation/test_llm_grounding.py
   ```

**Red Flags (LLM making things up):**
- Numbers don't match `data` field
- Mentions teams/players not in the query
- Statistics that seem too specific without backing data
- Contradicts the pipeline's recommendation

---

## Testing Follow-up Conversations

The hybrid approach maintains conversation history. Test this flow:

1. `Tell me about the Chiefs`
   → Get KC profile with natural language

2. `What about the Bills?`
   → Should understand "same analysis, different team"
   → Returns BUF profile naturally

3. `Compare them`
   → Knows "them" = Bills and Chiefs
   → Returns comparison in conversational style

---

## Testing Without LLM (Fallback)

To test the structured fallback when LLM is unavailable:

1. Set `use_llm: false` in the request
2. Or disable your OpenAI/Anthropic API key

Response should fall back to structured format:
```
**3rd & 5**
At the 40 yard line

**Expected Points Added:**
• Pass: +0.145
• Run: +0.111

**Recommendation: PASS** (57% confidence)
```

This ensures the chatbot works even without LLM access.
