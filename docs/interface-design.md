# Interface direction: black and blue

Inspected in Chrome on 16 October 2026:
- [Linear: A calmer interface for a product in motion](https://linear.app/now/behind-the-latest-design-refresh): restrained saturation, clear surface hierarchy, subtle boundaries, readable navigation.
- [Vercel Geist colors](https://vercel.com/geist/colors): semantic color roles and separate neutral and accent scales across light and dark modes.

Chalkmate uses its own palette and existing layouts. Dark is the initial preference; Light and System remain available and saved in Settings, including before login.

| Role | Dark | Light |
|---|---|---|
| Canvas | `#090B10` | `#F7F8FA` |
| Sidebar | `#0D1016` | `#F2F4F7` |
| Cards / dialogs | `#11141B` | `#FFFFFF` |
| Raised / hover surface | `#191D26` | `#F0F2F5` |
| Border | `#2A303D` | `#DFE3EB` |
| Heading | `#F3F5FA` | `#161B26` |
| Body | `#D3D7E0` | `#303746` |
| Secondary text | `#9BA4B5` | `#667085` |
| Primary button | `#306BEA` | `#245BD6` |
| Link / selection text | `#8BB5FF` | `#245BD6` |
| Selected background | `#16243E` | `#EDF3FF` |

Use blue for actions, focus, selected navigation, and compact labels. Keep large work surfaces neutral. Use red for errors and amber for warnings. Primary buttons use white text. Shared tokens cover authentication, classrooms, rosters, files, assessments, rubric editing, review, and settings. Original document pages keep their own colors inside a theme-aware viewer. System sans-serif headings replace the previous serif headings. No remote font dependency.

# Local account verification

This installation captures verification and recovery emails at <http://127.0.0.1:54324>. They do not arrive in external Gmail inboxes. The local-only explanation is rendered only for loopback Supabase on port 54321; hosted projects retain ordinary verification messaging. Email confirmation remains required.

To create a confirmed synthetic local test account with a demo workspace and classroom, run `.venv/Scripts/python.exe scripts/create_demo_account.py` while the API is running. The script refuses nonlocal or nondevelopment Supabase, preserves existing accounts, generates a random password, verifies sign-in and API access, and saves the reusable login in ignored `.tmp/demo-credentials.json`. Never copy that file into source control.

# Planning and motion refinement

The Planning studio uses compact tool tiles, a searchable versioned library and focused dialogs.
Introductory copy on classroom sections moves into Info buttons supporting hover, focus, tap
and Escape. Bubbles are positioned within the viewport and follow scrolling. Dialog titles
have unique accessible IDs. Important approval, recipient and source checks remain visible.

Use short entrance motion and press feedback; a finite wobble belongs on an interactive icon.
Never retain a transform after a panel entrance: that changes the containing block for fixed
help and can leak table overflow on mobile. Animation fill is backwards only. Reduced motion
disables animations/transitions. Mobile headings and the search field get their own rows;
wide rosters and classroom tabs scroll inside their own containers.
