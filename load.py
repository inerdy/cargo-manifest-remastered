import sys
import tkinter as tk
import requests
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb
from config import config
import json
from os import path
import tkinter.ttk as ttk
from datetime import datetime
import time
import threading



this = sys.modules[__name__]  # For holding module globals

def debug_log(message):
	"""Write debug messages to a log file"""
	try:
		directoryName = path.basename(path.dirname(__file__)) or 'CargoManifest'
		pluginPath = path.join(config.plugin_dir, directoryName)
		logPath = path.join(pluginPath, "debug.log")
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		with open(logPath, 'a', encoding='utf-8') as f:
			f.write(f"[{timestamp}] {message}\n")
	except:
		pass  # Silently fail if logging doesn't work

# Discord Rich Presence - using native implementation
DISCORD_RPC_AVAILABLE = True
debug_log("Discord Rich Presence available (native implementation)")

this.cargoDict = {}
this.eddbData = {}
this.inventory = []
this.cargoCapacity = "?"
this.cargoType = "Cargo"
this.tradeRank = "None"
this.tradeProgress = 0
this.explorationRank = "None"
this.explorationProgress = 0
this.credits = 0
this.webhookUrl = ""
this.enableWebhooks = False
this.currentStation = "Unknown"
this.currentSystem = "Unknown"
this.purchaseHistory = {}  # Track cargo purchases: {cargo_name: {quantity: int, avg_price: float, total_cost: int}}
this.commanderName = "Unknown"
this.webhookAvatar = ""  # Custom avatar URL for webhook
this.webhookBotName = "Cargo Manifest Bot"  # Custom bot name for webhook
this.webhookBotImage = ""  # Custom bot image URL for webhook
this.totalTradeProfit = 0  # Track total trade profits/losses
this.enableDiscordRPC = False  # Discord Status Updates setting
this.discordStatusWebhook = ""  # Separate webhook URL for status updates
this.discordRPCThread = None  # Thread for Discord status updates
this.lastStatusUpdate = 0  # Timestamp of last status update for rate limiting
this.budgetGoal = 0  # Credit goal for budget tracking
this.budgetEnabled = False  # Whether budget tracking is enabled
this.cargoRacks = []  # List of equipped cargo racks with their details

this.version = 'v3.0.3'

def checkVersion():
	try:
		req = requests.get(url='https://api.github.com/repos/inerdy/cargo-manifest-remastered/releases/latest')
	except:
		return -1
	if not req.status_code == requests.codes.ok:
		return -1 # Error
	data = req.json()
	if data['tag_name'] == this.version:
		return 1 # Newest
	return 0 # Newer version available

def get_current_commander():
	"""Try to get the current commander name from various sources"""
	try:
		# Try to get from EDMC's current commander
		from config import config
		current_cmdr = config.get_str('commander')
		if current_cmdr and current_cmdr != "Unknown":
			debug_log(f"Got commander name from EDMC config: {current_cmdr}")
			return current_cmdr
	except Exception as e:
		debug_log(f"Error getting commander from EDMC config: {e}")
	
	# Try to get from environment or other sources
	try:
		import os
		cmdr = os.environ.get('EDMC_COMMANDER')
		if cmdr:
			debug_log(f"Got commander name from environment: {cmdr}")
			return cmdr
	except:
		pass
	
	debug_log("Could not get commander name from any source")
	return "Unknown"

def plugin_start3(plugin_dir):
	debug_log("Plugin starting up...")
	# Read in item names on startup
	directoryName = path.basename(path.dirname(__file__)) or 'CargoManifest'
	pluginPath = path.join(config.plugin_dir, directoryName)
	filePath = path.join(pluginPath, "items.json")
	this.items = pullItems()
	if this.items == -1:
		# If error reaching EDCD github, use local copy
		this.items = json.loads(open(filePath, 'r').read())
	else:
		# If successful, save local copy
		with open(filePath, 'w') as f:
			f.write(json.dumps(this.items, indent=4, sort_keys=True))
	this.newest = checkVersion()
	
	# Load webhook settings on startup
	try:
		webhookUrlValue = config.get_str("cm_webhookUrl")
		debug_log(f"Startup - Loaded webhook URL: {webhookUrlValue}")
		this.webhookUrl = webhookUrlValue
	except:
		debug_log("Startup - No webhook URL found, using empty string")
		this.webhookUrl = ""
	
	try:
		enableWebhooksValue = config.get_bool("cm_enableWebhooks")
		debug_log(f"Startup - Loaded enable webhooks: {enableWebhooksValue}")
		this.enableWebhooks = enableWebhooksValue
	except:
		debug_log("Startup - No enable webhooks setting found, defaulting to False")
		this.enableWebhooks = False
	
	# Load avatar URL setting
	try:
		avatarUrlValue = config.get_str("cm_webhookAvatar")
		debug_log(f"Startup - Loaded webhook avatar URL: {avatarUrlValue}")
		this.webhookAvatar = avatarUrlValue
	except:
		debug_log("Startup - No webhook avatar URL found, using empty string")
		this.webhookAvatar = ""
	
	# Load bot name setting
	try:
		botNameValue = config.get_str("cm_webhookBotName")
		debug_log(f"Startup - Loaded webhook bot name: {botNameValue}")
		this.webhookBotName = botNameValue if botNameValue else "Cargo Manifest Bot"
	except:
		debug_log("Startup - No webhook bot name found, using default")
		this.webhookBotName = "Cargo Manifest Bot"
	
	# Load bot image setting
	try:
		botImageValue = config.get_str("cm_webhookBotImage")
		debug_log(f"Startup - Loaded webhook bot image URL: {botImageValue}")
		this.webhookBotImage = botImageValue
	except:
		debug_log("Startup - No webhook bot image found, using empty string")
		this.webhookBotImage = ""
	
	# Load Discord RPC setting
	try:
		discordRPCValue = config.get_bool("cm_enableDiscordRPC")
		debug_log(f"Startup - Loaded Discord RPC setting: {discordRPCValue}")
		this.enableDiscordRPC = discordRPCValue
	except:
		debug_log("Startup - No Discord RPC setting found, defaulting to False")
		this.enableDiscordRPC = False
	
	# Load Discord Status Webhook setting
	try:
		statusWebhookValue = config.get_str("cm_discordStatusWebhook")
		debug_log(f"Startup - Loaded Discord status webhook URL: {statusWebhookValue}")
		this.discordStatusWebhook = statusWebhookValue
	except:
		debug_log("Startup - No Discord status webhook found, using empty string")
		this.discordStatusWebhook = ""
	
	# Load budget settings
	try:
		budgetGoalValue = config.get_str("cm_budgetGoal")
		debug_log(f"Startup - Loaded budget goal: {budgetGoalValue}")
		# Convert string to integer for budget goal, handling large numbers
		try:
			this.budgetGoal = int(budgetGoalValue.replace(',', ''))
		except (ValueError, AttributeError):
			this.budgetGoal = 0
	except:
		debug_log("Startup - No budget goal found, defaulting to 0")
		this.budgetGoal = 0
	
	try:
		budgetEnabledValue = config.get_bool("cm_budgetEnabled")
		debug_log(f"Startup - Loaded budget enabled: {budgetEnabledValue}")
		this.budgetEnabled = budgetEnabledValue
	except:
		debug_log("Startup - No budget enabled setting found, defaulting to False")
		this.budgetEnabled = False
	
	# Initialize community goals data
	this.communityGoals = []
	this.currentCommunityGoal = None
	
	# Try to get community goals from EDMC state
	load_community_goals_from_edmc()
	
	# Set up periodic refresh of community goals (every 30 minutes)
	def periodic_community_goals_refresh():
		import threading
		import time
		
		while True:
			try:
				time.sleep(1800)  # 30 minutes
				debug_log("Periodic community goals refresh triggered")
				fetch_community_goals_fallback()
				update_community_goals_display()
			except Exception as e:
				debug_log(f"Error in periodic community goals refresh: {e}")
	
	# Start the background thread
	refresh_thread = threading.Thread(target=periodic_community_goals_refresh, daemon=True)
	refresh_thread.start()
	debug_log("Started periodic community goals refresh thread")
	

	
	
	# Initialize Discord Status Updates if enabled
	if this.enableDiscordRPC:
		init_discord_rpc()
	
	# Try to get commander name during startup
	this.commanderName = get_current_commander()
	
	debug_log("Plugin startup complete")
	return "Cargo Manifest Remastered"

def plugin_stop():
	"""Clean up when plugin is stopped"""
	cleanup_discord_rpc()
	debug_log("Plugin stopped")

def plugin_app(parent):
    # Adds to the main page UI
    this.frame = tk.Frame(parent)

    # Dropdown style logic for EDMC theme compatibility
    import tkinter.ttk as ttk
    style = ttk.Style()
    # Try to use EDMC's theme style if available, else define our own
    combobox_style = "TCombobox"
    # Check if EDMC.TCombobox or similar is available
    try:
        available_styles = list(style.element_names()) + list(style.layout("TCombobox"))
        if "EDMC.TCombobox" in style.theme_names() or "EDMC.TCombobox" in available_styles:
            combobox_style = "EDMC.TCombobox"
        else:
            # Fallback: define a custom black/orange style
            style.configure("EDMC.TCombobox",
                fieldbackground="#181818",
                background="#181818",
                foreground="#FFA500",
                selectforeground="#FFA500",
                selectbackground="#181818",
                arrowcolor="#FFA500",
                bordercolor="#FFA500",
                lightcolor="#181818",
                darkcolor="#181818",
                focuscolor="#FFA500"
            )
            # Also try to style the dropdown list
            style.map("EDMC.TCombobox",
                fieldbackground=[("readonly", "#181818")],
                background=[("readonly", "#181818")],
                foreground=[("readonly", "#FFA500")],
                selectbackground=[("readonly", "#181818")],
                selectforeground=[("readonly", "#FFA500")]
            )
            # Try to style the listbox part
            try:
                style.configure("EDMC.TCombobox.Listbox",
                    background="#181818",
                    foreground="#FFA500",
                    selectbackground="#181818",
                    selectforeground="#FFA500",
                    highlightbackground="#FFA500",
                    highlightcolor="#FFA500"
                )
            except:
                pass  # Listbox styling might not be supported
            combobox_style = "EDMC.TCombobox"
    except:
        # If style detection fails, use default TCombobox
        combobox_style = "TCombobox"
    # Now use combobox_style for the dropdown

    # Dropdown
    this.sectionVar = tk.StringVar()
    this.sectionDropdown = ttk.Combobox(
        this.frame,
        textvariable=this.sectionVar,
        		values=["Manifest", "Captain Information", "Budget", "Cargo Racks", "Community Goals"],
        state="readonly",
        width=20,
        style=combobox_style
    )
    this.sectionDropdown.grid(row=0, column=0, sticky="ew", pady=(2, 6))
    this.sectionDropdown.set("Manifest")

    # Captain Info Frame
    this.captainInfoFrame = tk.Frame(this.frame)
    this.captainInfoLabel = tk.Label(this.captainInfoFrame, justify="left", anchor="w")
    this.captainInfoLabel.pack(anchor="w", padx=4, pady=4)

    # Cargo Manifest Frame
    this.cargoManifestFrame = tk.Frame(this.frame)
    this.cargoManifestLabel = tk.Label(this.cargoManifestFrame, justify="left", anchor="w")
    this.cargoManifestLabel.pack(anchor="w", padx=4, pady=4)

    # Budget Frame
    this.budgetFrame = tk.Frame(this.frame)
    this.budgetLabel = tk.Label(this.budgetFrame, justify="left", anchor="w")
    this.budgetLabel.pack(anchor="w", padx=4, pady=4)

    # Cargo Racks Frame
    this.cargoRacksFrame = tk.Frame(this.frame)
    this.cargoRacksLabel = tk.Label(this.cargoRacksFrame, justify="left", anchor="w")
    this.cargoRacksLabel.pack(anchor="w", padx=4, pady=4)

    # Community Goals Frame
    this.communityGoalsFrame = tk.Frame(this.frame)
    this.communityGoalsLabel = tk.Label(this.communityGoalsFrame, justify="left", anchor="w", wraplength=400)
    this.communityGoalsLabel.pack(anchor="w", padx=4, pady=4)

    # Show only the selected frame
    def show_section(*_):
        if this.sectionVar.get() == "Manifest":
            this.captainInfoFrame.grid_forget()
            this.budgetFrame.grid_forget()
            this.cargoRacksFrame.grid_forget()
            this.communityGoalsFrame.grid_forget()
            this.cargoManifestFrame.grid(row=1, column=0, sticky="nsew")
            update_cargo_manifest_display()
        elif this.sectionVar.get() == "Captain Information":
            this.cargoManifestFrame.grid_forget()
            this.budgetFrame.grid_forget()
            this.cargoRacksFrame.grid_forget()
            this.communityGoalsFrame.grid_forget()
            this.captainInfoFrame.grid(row=1, column=0, sticky="nsew")
            update_captain_info_display()
        elif this.sectionVar.get() == "Budget":
            this.cargoManifestFrame.grid_forget()
            this.captainInfoFrame.grid_forget()
            this.cargoRacksFrame.grid_forget()
            this.communityGoalsFrame.grid_forget()
            this.budgetFrame.grid(row=1, column=0, sticky="nsew")
            update_budget_display()
        elif this.sectionVar.get() == "Cargo Racks":
            this.cargoManifestFrame.grid_forget()
            this.captainInfoFrame.grid_forget()
            this.budgetFrame.grid_forget()
            this.communityGoalsFrame.grid_forget()
            this.cargoRacksFrame.grid(row=1, column=0, sticky="nsew")
            update_cargo_racks_display()
        elif this.sectionVar.get() == "Community Goals":
            debug_log("Switching to Community Goals section")
            this.cargoManifestFrame.grid_forget()
            this.captainInfoFrame.grid_forget()
            this.budgetFrame.grid_forget()
            this.cargoRacksFrame.grid_forget()
            this.communityGoalsFrame.grid(row=1, column=0, sticky="nsew")
            update_community_goals_display()

    this.sectionDropdown.bind("<<ComboboxSelected>>", show_section)

    # Initial display
    show_section()

    return this.frame

def plugin_prefs(parent, cmdr, is_beta):
	# Adds page to settings menu
	frame = nb.Frame(parent)
	
	# Create a canvas with scrollbar for scrollable settings
	canvas = tk.Canvas(frame)
	scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
	scrollable_frame = tk.Frame(canvas)
	
	scrollable_frame.bind(
		"<Configure>",
		lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
	)
	
	canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
	canvas.configure(yscrollcommand=scrollbar.set)
	
	# Grid the canvas and scrollbar
	canvas.grid(row=0, column=0, sticky="nsew")
	scrollbar.grid(row=0, column=1, sticky="ns")
	
	# Configure grid weights for proper expansion
	frame.grid_rowconfigure(0, weight=1)
	frame.grid_columnconfigure(0, weight=1)
	this.hideUpdate = tk.BooleanVar(value=config.get_bool("cm_hideUpdate"))
	
	# Handle default value for showTradeRank setting
	try:
		showTradeRankValue = config.get_bool("cm_showTradeRank")
	except:
		showTradeRankValue = True  # Default to True if setting doesn't exist
	this.showTradeRank = tk.BooleanVar(value=showTradeRankValue)
	
	# Handle default value for showCredits setting
	try:
		showCreditsValue = config.get_bool("cm_showCredits")
	except:
		showCreditsValue = True  # Default to True if setting doesn't exist
	this.showCredits = tk.BooleanVar(value=showCreditsValue)
	
	# Handle webhook settings
	try:
		webhookUrlValue = config.get_str("cm_webhookUrl")
		debug_log(f"Loaded webhook URL: {webhookUrlValue}")
	except:
		webhookUrlValue = ""
		debug_log("No webhook URL found, using empty string")
	this.webhookUrlVar = tk.StringVar(value=webhookUrlValue)
	
	try:
		enableWebhooksValue = config.get_bool("cm_enableWebhooks")
		debug_log(f"Loaded enable webhooks: {enableWebhooksValue}")
	except:
		enableWebhooksValue = False
		debug_log("No enable webhooks setting found, defaulting to False")
	this.enableWebhooksVar = tk.BooleanVar(value=enableWebhooksValue)
	
	# Handle avatar URL setting
	try:
		avatarUrlValue = config.get_str("cm_webhookAvatar")
		debug_log(f"Loaded webhook avatar URL: {avatarUrlValue}")
	except:
		avatarUrlValue = ""
		debug_log("No webhook avatar URL found, using empty string")
	this.webhookAvatarVar = tk.StringVar(value=avatarUrlValue)
	
	# Handle bot name setting
	try:
		botNameValue = config.get_str("cm_webhookBotName")
		debug_log(f"Loaded webhook bot name: {botNameValue}")
	except:
		botNameValue = "Cargo Manifest Bot"
		debug_log("No webhook bot name found, using default")
	this.webhookBotNameVar = tk.StringVar(value=botNameValue)
	
	# Handle bot image setting
	try:
		botImageValue = config.get_str("cm_webhookBotImage")
		debug_log(f"Loaded webhook bot image URL: {botImageValue}")
	except:
		botImageValue = ""
		debug_log("No webhook bot image URL found, using empty string")
	this.webhookBotImageVar = tk.StringVar(value=botImageValue)
	
	# Handle Discord RPC setting
	try:
		discordRPCValue = config.get_bool("cm_enableDiscordRPC")
		debug_log(f"Loaded Discord RPC setting: {discordRPCValue}")
	except:
		discordRPCValue = False
		debug_log("No Discord RPC setting found, defaulting to False")
	this.enableDiscordRPCVar = tk.BooleanVar(value=discordRPCValue)
	
	# Handle Discord Status Webhook setting
	try:
		statusWebhookValue = config.get_str("cm_discordStatusWebhook")
		debug_log(f"Loaded Discord status webhook URL: {statusWebhookValue}")
	except:
		statusWebhookValue = ""
		debug_log("No Discord status webhook found, using empty string")
	this.discordStatusWebhookVar = tk.StringVar(value=statusWebhookValue)
	
	# Handle budget settings
	try:
		budgetGoalValue = config.get_str("cm_budgetGoal")
		debug_log(f"Loaded budget goal: {budgetGoalValue}")
	except:
		budgetGoalValue = "0"
		debug_log("No budget goal found, defaulting to 0")
	this.budgetGoalVar = tk.StringVar(value=budgetGoalValue)
	
	try:
		budgetEnabledValue = config.get_bool("cm_budgetEnabled")
		debug_log(f"Loaded budget enabled: {budgetEnabledValue}")
	except:
		budgetEnabledValue = False
		debug_log("No budget enabled setting found, defaulting to False")
	this.budgetEnabledVar = tk.BooleanVar(value=budgetEnabledValue)
	

	
	# Title and version
	tk.Label(scrollable_frame, text="Cargo Manifest Remastered {}".format(this.version), background=nb.Label().cget('background'), font=("TkDefaultFont", 10, "bold")).grid(sticky="w", pady=(0, 10))
	
	# Manifest Display Settings
	tk.Label(scrollable_frame, text="Manifest Display:", background=nb.Label().cget('background'), font=("TkDefaultFont", 9, "bold")).grid(sticky="w", pady=(0, 5))
	tk.Checkbutton(scrollable_frame, text="Hide update available indicator (not recommended)", variable=this.hideUpdate, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	tk.Checkbutton(scrollable_frame, text="Show trade rank in manifest", variable=this.showTradeRank, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	tk.Checkbutton(scrollable_frame, text="Show credits in manifest", variable=this.showCredits, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	
	# Discord Webhook Settings
	tk.Label(scrollable_frame, text="Discord Webhooks:", background=nb.Label().cget('background'), font=("TkDefaultFont", 9, "bold")).grid(sticky="w", pady=(15, 5))
	tk.Checkbutton(scrollable_frame, text="Enable Discord webhooks", variable=this.enableWebhooksVar, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	tk.Label(scrollable_frame, text="Webhook URL:", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	webhookEntry = tk.Entry(scrollable_frame, textvariable=this.webhookUrlVar, width=50)
	webhookEntry.grid(sticky="ew", pady=(2, 5))
	
	tk.Label(scrollable_frame, text="Bot Name (optional):", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	botNameEntry = tk.Entry(scrollable_frame, textvariable=this.webhookBotNameVar, width=50)
	botNameEntry.grid(sticky="ew", pady=(2, 5))
	
	tk.Label(scrollable_frame, text="Avatar URL (optional):", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	avatarEntry = tk.Entry(scrollable_frame, textvariable=this.webhookAvatarVar, width=50)
	avatarEntry.grid(sticky="ew", pady=(2, 5))
	
	tk.Label(scrollable_frame, text="Bot Image URL (optional):", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	botImageEntry = tk.Entry(scrollable_frame, textvariable=this.webhookBotImageVar, width=50)
	botImageEntry.grid(sticky="ew", pady=(2, 5))
	
	# Discord Status Updates Settings
	tk.Label(scrollable_frame, text="Discord Status Updates:", background=nb.Label().cget('background'), font=("TkDefaultFont", 9, "bold")).grid(sticky="w", pady=(15, 5))
	tk.Checkbutton(scrollable_frame, text="Enable Discord Status Updates", variable=this.enableDiscordRPCVar, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	tk.Label(scrollable_frame, text="Status Webhook URL:", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	statusWebhookEntry = tk.Entry(scrollable_frame, textvariable=this.discordStatusWebhookVar, width=50)
	statusWebhookEntry.grid(sticky="ew", pady=(2, 5))
	tk.Label(scrollable_frame, text="Separate webhook for status updates (optional)", background=nb.Label().cget('background'), foreground="gray").grid(sticky="w", pady=(0, 5))
	
	# Budget Settings
	tk.Label(scrollable_frame, text="Budget Tracking:", background=nb.Label().cget('background'), font=("TkDefaultFont", 9, "bold")).grid(sticky="w", pady=(15, 5))
	tk.Checkbutton(scrollable_frame, text="Enable budget tracking", variable=this.budgetEnabledVar, background=nb.Label().cget('background')).grid(sticky="w", pady=1)
	tk.Label(scrollable_frame, text="Credit Goal:", background=nb.Label().cget('background')).grid(sticky="w", pady=(5, 0))
	budgetGoalEntry = tk.Entry(scrollable_frame, textvariable=this.budgetGoalVar, width=30)
	budgetGoalEntry.grid(sticky="w", pady=(2, 5))
	tk.Label(scrollable_frame, text="Set your target credit amount (supports large numbers like 1,000,000,000)", background=nb.Label().cget('background'), foreground="gray").grid(sticky="w", pady=(0, 5))
	

	
	# Credits section
	tk.Label(scrollable_frame, text="", background=nb.Label().cget('background')).grid(sticky="w", pady=(20, 5))  # Spacer
	tk.Label(scrollable_frame, text="Credits:", background=nb.Label().cget('background'), font=("TkDefaultFont", 9, "bold")).grid(sticky="w", pady=(0, 5))
	HyperlinkLabel(scrollable_frame, text="Original plugin by RemainNA", background=nb.Label().cget('background'), url="https://github.com/RemainNA/cargo-manifest").grid(sticky="w", pady=(0, 5))
	
	return frame

def prefs_changed(cmdr, is_beta):
	# Safety check - only save settings if UI variables exist
	if hasattr(this, 'hideUpdate'):
		config.set("cm_hideUpdate", this.hideUpdate.get())
	if hasattr(this, 'showTradeRank'):
		config.set("cm_showTradeRank", this.showTradeRank.get())
	if hasattr(this, 'showCredits'):
		config.set("cm_showCredits", this.showCredits.get())
	if hasattr(this, 'webhookUrlVar'):
		config.set("cm_webhookUrl", this.webhookUrlVar.get())
	if hasattr(this, 'enableWebhooksVar'):
		config.set("cm_enableWebhooks", this.enableWebhooksVar.get())
	if hasattr(this, 'webhookAvatarVar'):
		config.set("cm_webhookAvatar", this.webhookAvatarVar.get())
	if hasattr(this, 'webhookBotNameVar'):
		config.set("cm_webhookBotName", this.webhookBotNameVar.get())
	if hasattr(this, 'webhookBotImageVar'):
		config.set("cm_webhookBotImage", this.webhookBotImageVar.get())
	if hasattr(this, 'enableDiscordRPCVar'):
		config.set("cm_enableDiscordRPC", this.enableDiscordRPCVar.get())
	if hasattr(this, 'discordStatusWebhookVar'):
		config.set("cm_discordStatusWebhook", this.discordStatusWebhookVar.get())
	if hasattr(this, 'budgetEnabledVar'):
		config.set("cm_budgetEnabled", this.budgetEnabledVar.get())
	if hasattr(this, 'budgetGoalVar'):
		config.set("cm_budgetGoal", this.budgetGoalVar.get())


	
	# Update global variables
	if hasattr(this, 'webhookUrlVar'):
		this.webhookUrl = this.webhookUrlVar.get()
	if hasattr(this, 'enableWebhooksVar'):
		this.enableWebhooks = this.enableWebhooksVar.get()
	if hasattr(this, 'webhookAvatarVar'):
		this.webhookAvatar = this.webhookAvatarVar.get()
	if hasattr(this, 'webhookBotNameVar'):
		this.webhookBotName = this.webhookBotNameVar.get() if this.webhookBotNameVar.get() else "Cargo Manifest Bot"
	if hasattr(this, 'webhookBotImageVar'):
		this.webhookBotImage = this.webhookBotImageVar.get()
	if hasattr(this, 'discordStatusWebhookVar'):
		this.discordStatusWebhook = this.discordStatusWebhookVar.get()
	if hasattr(this, 'budgetEnabledVar'):
		this.budgetEnabled = this.budgetEnabledVar.get()
	if hasattr(this, 'budgetGoalVar'):
		# Convert string to integer for budget goal, handling large numbers
		try:
			this.budgetGoal = int(this.budgetGoalVar.get().replace(',', ''))
		except (ValueError, AttributeError):
			this.budgetGoal = 0

	
	# Handle Discord RPC setting change
	if hasattr(this, 'enableDiscordRPCVar'):
		oldDiscordRPC = this.enableDiscordRPC
		this.enableDiscordRPC = this.enableDiscordRPCVar.get()
		
		# Initialize or cleanup Discord RPC based on setting
		if this.enableDiscordRPC and not oldDiscordRPC:
			init_discord_rpc()
		elif not this.enableDiscordRPC and oldDiscordRPC:
			cleanup_discord_rpc()
	
	debug_log(f"Settings saved - webhookUrl: {this.webhookUrl}, enableWebhooks: {this.enableWebhooks}, avatarUrl: {this.webhookAvatar}, botName: {this.webhookBotName}, botImage: {this.webhookBotImage}, discordRPC: {this.enableDiscordRPC}, statusWebhook: {this.discordStatusWebhook}")
	
	update_display()
	# Update budget display if settings changed
	if this.budgetEnabled:
		update_budget_display()

def pullItems():
	items = {}

	# Fetch commodity data from EDCD github
	try:
		commodities = requests.get('https://raw.githubusercontent.com/EDCD/FDevIDs/master/commodity.csv')
		rareCommodities = requests.get('https://raw.githubusercontent.com/EDCD/FDevIDs/master/rare_commodity.csv')
	except:
		return -1

	if not commodities.status_code == requests.codes.ok or not rareCommodities.status_code == requests.codes.ok:
		return -1 # Error

	for c in commodities.text.split('\n'):
		line = c.strip().split(',')
		if line[0] == 'id' or c == '':
			continue
		items[line[1].lower()] = {'id':line[0], 'category':line[2], 'name':line[3]}

	for c in rareCommodities.text.split('\n'):
		line = c.strip().split(',')
		if line[0] == 'id' or c == '':
			continue
		items[line[1].lower()] = {'id':line[0], 'category':line[3], 'name':line[4]}
	return items

def journal_entry(cmdr, is_beta, system, station, entry, state):
	# Parse journal entries
	debug_log(f"Journal event received: {entry['event']}")
	
	# Update commander name from the cmdr parameter if available
	if cmdr and cmdr != "Unknown":
		if this.commanderName == "Unknown" or this.commanderName != cmdr:
			this.commanderName = cmdr
			debug_log(f"Commander name updated from cmdr parameter: {this.commanderName}")
	
	# Update system and station from parameters if available
	if system and system != "Unknown":
		if this.currentSystem == "Unknown" or this.currentSystem != system:
			this.currentSystem = system
			debug_log(f"System updated from parameter: {this.currentSystem}")
	
	if station and station != "Unknown":
		if this.currentStation == "Unknown" or this.currentStation != station:
			this.currentStation = station
			debug_log(f"Station updated from parameter: {this.currentStation}")
	
	if entry['event'] == 'Cargo':
		# Emitted whenever cargo hold updates
		if state['Cargo'] != this.cargoDict:
			this.cargoDict = state['Cargo']
		if 'Inventory' in entry and entry['Inventory'] != this.inventory:
			this.inventory = entry['Inventory']
		# Debug: Check what's available in state
		debug_log(f"Cargo event - State keys: {list(state.keys())}")
		if 'Rank' in state:
			debug_log(f"Cargo event - Rank data: {state['Rank']}")
		# Check for rank data in state during cargo updates
		if 'Rank' in state:
			update_ranks(state['Rank'])
		update_display()
		# Update captain info display specifically to ensure ranks are shown
		update_captain_info_display()
		# Update cargo manifest display specifically to ensure cargo data is shown
		update_cargo_manifest_display()
		# Update Discord status when cargo changes
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Loadout':
		# Emitted when loadout changes
		if this.cargoCapacity != entry['CargoCapacity']:
			this.cargoCapacity = entry['CargoCapacity']
		# Detect cargo type from modules
		this.cargoType = detect_cargo_type(entry['Modules'])
		update_display()
		# Update cargo manifest display specifically to ensure cargo capacity is shown
		update_cargo_manifest_display()
		# Update cargo racks display specifically to ensure racks are shown
		update_cargo_racks_display()
		# Update Discord status when loadout changes (ship modifications)
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Rank':
		# Emitted when any rank changes
		debug_log(f"Rank event received: {entry}")  # Debug
		update_ranks(entry)
		update_display()
		# Update captain info display specifically to ensure ranks are shown
		update_captain_info_display()
		# Update Discord status when ranks change (progression)
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Credits':
		# Emitted when credits change
		debug_log(f"Credits event received: {entry}")  # Debug
		if 'Credits' in entry:
			update_credits(entry['Credits'])
			update_display()
			# Update captain info display specifically to ensure credits are shown
			update_captain_info_display()
			# Update budget display when credits change
			if this.budgetEnabled:
				update_budget_display()
			# Update Discord status when credits change (trading activity)
			if this.enableDiscordRPC:
				update_discord_status()
		# Also check state for credits (in case entry doesn't have them)
		elif 'Credits' in state and state['Credits'] != this.credits:
			debug_log(f"Credits updated from state during Credits event: {state['Credits']} (was: {this.credits})")
			update_credits(state['Credits'])
			update_captain_info_display()
			if this.budgetEnabled:
				update_budget_display()
	
	elif entry['event'] == 'MarketSell':
		# Emitted when cargo is sold at market
		debug_log(f"MarketSell event received: {entry}")  # Debug
		handle_market_sell(entry)
		# Update credits from state if available
		if 'Credits' in state and state['Credits'] != this.credits:
			debug_log(f"Credits updated from state after MarketSell: {state['Credits']} (was: {this.credits})")
			update_credits(state['Credits'])
			update_captain_info_display()
		# Update budget display when credits change from sales
		if this.budgetEnabled:
			update_budget_display()
		
		# Refresh community goals after selling cargo (might be related to community goals)
		fetch_community_goals_fallback()
		update_community_goals_display()
		
		# Update Discord status when trading
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'MarketBuy':
		# Emitted when cargo is bought at market
		debug_log(f"MarketBuy event received: {entry}")  # Debug
		handle_market_buy(entry)
		# Update credits from state if available
		if 'Credits' in state and state['Credits'] != this.credits:
			debug_log(f"Credits updated from state after MarketBuy: {state['Credits']} (was: {this.credits})")
			update_credits(state['Credits'])
			update_captain_info_display()
		# Update budget display when credits change from purchases
		if this.budgetEnabled:
			update_budget_display()
		
		# Refresh community goals after buying cargo (might be related to community goals)
		fetch_community_goals_fallback()
		update_community_goals_display()
		
		# Update Discord status when trading
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Location':
		# Emitted when location changes (system, station, etc.)
		debug_log(f"Location event received: {entry}")  # Debug
		if 'StationName' in entry:
			this.currentStation = entry['StationName']
			debug_log(f"Updated station to: {this.currentStation}")
		if 'StarSystem' in entry:
			this.currentSystem = entry['StarSystem']
			debug_log(f"Updated system to: {this.currentSystem}")
		# Update Discord status when location changes
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Docked':
		# Emitted when docking at a station
		debug_log(f"Docked event received: {entry}")  # Debug
		if 'StationName' in entry:
			this.currentStation = entry['StationName']
			debug_log(f"Updated station to: {this.currentStation}")
		if 'StarSystem' in entry:
			this.currentSystem = entry['StarSystem']
			debug_log(f"Updated system to: {this.currentSystem}")
		# Update Discord status when docking
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Undocked':
		# Emitted when undocking from a station
		debug_log(f"Undocked event received: {entry}")  # Debug
		this.currentStation = "Unknown"  # Reset station when undocking
		debug_log(f"Reset station to: Unknown (undocked)")
		# Update Discord status when undocking
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Liftoff':
		# Emitted when taking off from a planet/station
		debug_log(f"Liftoff event received: {entry}")  # Debug
		this.currentStation = "Unknown"  # Reset station when taking off
		debug_log(f"Reset station to: Unknown (liftoff)")
		# Update Discord status when taking off
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'FSDJump':
		# Emitted when jumping to another system
		debug_log(f"FSDJump event received: {entry}")  # Debug
		this.currentStation = "Unknown"  # Reset station when jumping
		if 'StarSystem' in entry:
			this.currentSystem = entry['StarSystem']
			debug_log(f"Updated system to: {this.currentSystem}")
		debug_log(f"Reset station to: Unknown (FSD jump)")
		# Update Discord status when jumping
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'Commander':
		# Emitted when commander data is loaded, contains rank information
		debug_log(f"Commander event received: {entry}")  # Debug
		debug_log(f"Commander event keys: {list(entry.keys())}")
		if 'Name' in entry:
			this.commanderName = entry['Name']
			debug_log(f"Commander name updated from Commander event: {this.commanderName}")
		else:
			debug_log(f"Commander event received but no Name field found")
		if 'Rank' in entry:
			debug_log(f"Commander - Rank data: {entry['Rank']}")
			update_ranks(entry['Rank'])
		if 'Credits' in entry:
			debug_log(f"Commander - Credits: {entry['Credits']}")
			update_credits(entry['Credits'])
		update_display()
		# Update captain info display specifically to ensure commander data is shown
		update_captain_info_display()
		# Update budget display when credits change from commander data
		if this.budgetEnabled:
			update_budget_display()
		# Update Discord status when commander data is loaded
		if this.enableDiscordRPC:
			update_discord_status()
		# Also check state for credits
		if 'Credits' in state and state['Credits'] != this.credits:
			debug_log(f"Credits updated from state during Commander event: {state['Credits']} (was: {this.credits})")
			update_credits(state['Credits'])
			update_captain_info_display()
			if this.budgetEnabled:
				update_budget_display()
	
	elif entry['event'] == 'CommunityGoal':
		# Emitted when community goal data is received
		debug_log(f"CommunityGoal event received: {entry}")
		handle_community_goal(entry)
	
	elif entry['event'] == 'LoadGame':
		# Emitted when loading into the game
		debug_log(f"LoadGame event received: {entry}")
		debug_log(f"LoadGame event keys: {list(entry.keys())}")
		if 'Commander' in entry:
			this.commanderName = entry['Commander']
			debug_log(f"Commander name updated from LoadGame event: {this.commanderName}")
		elif 'Name' in entry:
			this.commanderName = entry['Name']
			debug_log(f"Commander name updated from LoadGame event: {this.commanderName}")
		else:
			debug_log(f"LoadGame event received but no commander name found")
		# Update credits from state if available
		if 'Credits' in state and state['Credits'] != this.credits:
			debug_log(f"Credits updated from state during LoadGame: {state['Credits']} (was: {this.credits})")
			update_credits(state['Credits'])
			update_captain_info_display()
		# Update Discord status when loading into the game
		if this.enableDiscordRPC:
			update_discord_status()
	
	elif entry['event'] == 'FileHeader':
		# Emitted at the start of each journal file, often contains commander name
		debug_log(f"FileHeader event received: {entry}")
		debug_log(f"FileHeader event keys: {list(entry.keys())}")
		if 'part' in entry and entry['part'] == 1:  # Only process the first part
			if 'Commander' in entry:
				this.commanderName = entry['Commander']
				debug_log(f"Commander name updated from FileHeader event: {this.commanderName}")
			elif 'Name' in entry:
				this.commanderName = entry['Name']
				debug_log(f"Commander name updated from FileHeader event: {this.commanderName}")
			else:
				debug_log(f"FileHeader event received but no commander name found")
	
	elif entry['event'] == 'StartUp':
		# Tries to update display from EDMC stored data when started after the game
		this.cargoDict = state['Cargo']
		try:
			this.inventory = state['CargoJSON']['Inventory'] # Only supported in 4.1.6 on
		except:
			pass
		
		# Use the stored cargo capacity from state instead of recalculating
		if 'CargoCapacity' in state:
			this.cargoCapacity = state['CargoCapacity']
		else:
			# Fallback to manual calculation if CargoCapacity not available
			cargoCap = 0
			for i in state['Modules']:
				item = state['Modules'][i]['Item']
				# Parse cargo rack capacity based on size and class
				if item.startswith('int_cargorack_size'):
					# Extract size and class from item name
					parts = item.split('_')
					if len(parts) >= 5:
						size = int(parts[3].replace('size', ''))
						class_num = int(parts[4].replace('class', ''))
						
						# Calculate capacity based on size and class
						base_capacity = 2 ** size  # Size 1=2, Size 2=4, Size 3=8, etc.
						if class_num == 8:
							# Class 8 racks have 1.5x capacity
							cargoCap += int(base_capacity * 1.5)
						else:
							# Standard class racks
							cargoCap += base_capacity
			this.cargoCapacity = cargoCap

		# Detect cargo type from modules
		this.cargoType = detect_cargo_type(state['Modules'])
		debug_log(f"Startup - Cargo type detected: {this.cargoType}, Cargo racks found: {len(this.cargoRacks)}")
		
		# Load rank data from state
		debug_log(f"StartUp state keys: {list(state.keys())}")  # Debug
		if 'Rank' in state:
			debug_log(f"Rank in state: {state['Rank']}")  # Debug
			update_ranks(state['Rank'])
		else:
			debug_log("No Rank found in state")
			# Try alternative ways to get rank data
			for key in state.keys():
				if 'rank' in key.lower():
					debug_log(f"Found potential rank key: {key} = {state[key]}")
		
		# Load credits data from state
		if 'Credits' in state:
			debug_log(f"Credits in state: {state['Credits']}")  # Debug
			update_credits(state['Credits'])
		else:
			debug_log("No Credits found in state")
		
		# Load location data from state
		if 'StationName' in state:
			this.currentStation = state['StationName']
			debug_log(f"StartUp - Loaded station: {this.currentStation}")
		
		# Try multiple possible system name keys
		if 'StarSystem' in state:
			this.currentSystem = state['StarSystem']
			debug_log(f"StartUp - Loaded system from StarSystem: {this.currentSystem}")
		elif 'SystemName' in state:
			this.currentSystem = state['SystemName']
			debug_log(f"StartUp - Loaded system from SystemName: {this.currentSystem}")
		elif 'System' in state:
			this.currentSystem = state['System']
			debug_log(f"StartUp - Loaded system from System: {this.currentSystem}")
		else:
			debug_log("StartUp - No system name found in state")
		
		# Load commander name from state
		debug_log(f"StartUp - Checking for commander data...")
		if 'Captain' in state:
			debug_log(f"StartUp - Captain data found: {state['Captain']}")
			if 'Name' in state['Captain']:
				this.commanderName = state['Captain']['Name']
				debug_log(f"StartUp - Loaded commander name from Captain: {this.commanderName}")
			else:
				debug_log(f"StartUp - Captain found but no Name field")
		elif 'Commander' in state:
			debug_log(f"StartUp - Commander data found: {state['Commander']}")
			if 'Name' in state['Commander']:
				this.commanderName = state['Commander']['Name']
				debug_log(f"StartUp - Loaded commander name from Commander: {this.commanderName}")
			else:
				debug_log(f"StartUp - Commander found but no Name field")
		else:
			debug_log("StartUp - No Captain or Commander data found in state")
		
		# Check all keys that might contain commander info
		for key in state.keys():
			if 'commander' in key.lower() or 'captain' in key.lower() or 'name' in key.lower():
				debug_log(f"StartUp - Potential commander key '{key}': {state[key]}")
		
		# Fallback: Try to get commander name from EDMC's current commander
		if this.commanderName == "Unknown":
			try:
				# Try to get the current commander from EDMC's state
				from config import config
				current_cmdr = config.get_str('commander')
				if current_cmdr:
					this.commanderName = current_cmdr
					debug_log(f"StartUp - Loaded commander name from EDMC config: {this.commanderName}")
				else:
					debug_log("StartUp - No commander name found in EDMC config")
			except Exception as e:
				debug_log(f"StartUp - Error getting commander from EDMC config: {e}")

		update_display()
		# Update cargo manifest display specifically to ensure it loads properly
		update_cargo_manifest_display()
		# Update captain info display specifically to ensure commander data is shown
		update_captain_info_display()
		# Update cargo racks display specifically to ensure racks are shown
		update_cargo_racks_display()
		# Update budget display if enabled
		if this.budgetEnabled:
			update_budget_display()
		# Update Discord status when game starts up
		if this.enableDiscordRPC:
			update_discord_status()
		
		# Check for community goals in state
		check_state_for_community_goals(state)

def detect_cargo_type(modules):
	"""Detect cargo type based on installed modules"""
	this.cargoRacks = []  # Reset cargo racks list
	cargo_type = "Cargo"  # Default cargo type
	
	debug_log(f"Detecting cargo type from {len(modules)} modules")
	
	# Log all modules for debugging
	all_modules = list(modules.items())
	debug_log(f"All modules: {[module_data['Item'] for module_id, module_data in all_modules]}")
	
	# Log modules that might be cargo racks
	cargo_like_modules = [module_data['Item'] for module_id, module_data in all_modules 
	                     if 'cargo' in module_data['Item'].lower() or 'rack' in module_data['Item'].lower()]
	debug_log(f"Cargo-like modules: {cargo_like_modules}")
	
	for module_id, module_data in modules.items():
		item = module_data['Item']
		debug_log(f"Checking module: {item}")
		
		if 'refinery' in item.lower():
			debug_log("Found refinery module")
			return "Refinery"
		elif 'limpet' in item.lower():
			debug_log("Found limpet module")
			return "Limpet"
		elif 'cargo' in item.lower():
			debug_log(f"Found cargo module: {item}")
			# Check for MK II racks specifically
			if 'mk' in item.lower() and 'ii' in item.lower():
				debug_log(f"*** MK II CARGO RACK DETECTED: {item} ***")
			# Special logging for Size 8 racks
			if 'size8' in item.lower():
				debug_log(f"*** SIZE 8 CARGO RACK: {item} ***")
			# Add cargo rack to the list
			rack_info = parse_cargo_rack(item, module_data)
			if rack_info:
				this.cargoRacks.append(rack_info)
				debug_log(f"Added cargo rack: {rack_info['name']} with capacity {rack_info['capacity']}")
			else:
				debug_log(f"Failed to parse cargo rack: {item}")
				# Special debug for MK II racks
				if 'mk' in item.lower() and 'ii' in item.lower():
					debug_log(f"MK II cargo rack detected but not parsed: {item}")
					debug_log(f"Full module data for MK II rack: {module_data}")
			# Don't return here - continue checking for more cargo racks
			cargo_type = "Cargo"
		elif 'mk' in item.lower() and 'ii' in item.lower():
			debug_log(f"*** MK II MODULE DETECTED (not cargo): {item} ***")
			# Check if this might be a cargo rack even if it doesn't contain 'cargo'
			if 'rack' in item.lower() or 'cargo' in item.lower():
				debug_log(f"*** MK II CARGO RACK DETECTED: {item} ***")
				rack_info = parse_cargo_rack(item, module_data)
				if rack_info:
					this.cargoRacks.append(rack_info)
					debug_log(f"Added MK II cargo rack: {rack_info['name']} with capacity {rack_info['capacity']}")
				else:
					debug_log(f"Failed to parse MK II cargo rack: {item}")
				cargo_type = "Cargo"
		elif 'mk' in item.lower():
			debug_log(f"*** MK MODULE DETECTED: {item} ***")
			# Check for any MK variant cargo racks
			if 'rack' in item.lower() or 'cargo' in item.lower():
				debug_log(f"*** MK CARGO RACK DETECTED: {item} ***")
				rack_info = parse_cargo_rack(item, module_data)
				if rack_info:
					this.cargoRacks.append(rack_info)
					debug_log(f"Added MK cargo rack: {rack_info['name']} with capacity {rack_info['capacity']}")
				else:
					debug_log(f"Failed to parse MK cargo rack: {item}")
				cargo_type = "Cargo"
		elif 'rack' in item.lower():
			debug_log(f"*** RACK MODULE DETECTED: {item} ***")
			# Check for any rack that might be cargo-related
			if 'cargo' in item.lower() or 'mk' in item.lower():
				debug_log(f"*** POTENTIAL CARGO RACK: {item} ***")
				rack_info = parse_cargo_rack(item, module_data)
				if rack_info:
					this.cargoRacks.append(rack_info)
					debug_log(f"Added potential cargo rack: {rack_info['name']} with capacity {rack_info['capacity']}")
				else:
					debug_log(f"Failed to parse potential cargo rack: {item}")
				cargo_type = "Cargo"
	
	debug_log(f"Finished checking modules. Found {len(this.cargoRacks)} cargo racks")
	
	# Calculate total detected capacity
	detected_capacity = sum(rack['capacity'] for rack in this.cargoRacks)
	debug_log(f"Total detected capacity: {detected_capacity}")
	
	# Compare with actual cargo capacity if available
	if hasattr(this, 'cargoCapacity') and this.cargoCapacity != "?":
		try:
			actual_capacity = int(this.cargoCapacity)
			debug_log(f"Actual cargo capacity: {actual_capacity}")
			if actual_capacity > detected_capacity:
				missing_capacity = actual_capacity - detected_capacity
				debug_log(f"Missing capacity: {missing_capacity} tons - likely MK II racks not detected")
				
				# Try to add missing MK II racks based on capacity
				if missing_capacity == 384:
					debug_log("Adding missing MK II Cargo Rack (Size 8) - 384 tons")
					this.cargoRacks.append({
						'name': "MK II Cargo Rack (Size 8)",
						'capacity': 384,
						'size': 8,
						'class': 8,
						'item_name': "mk_ii_cargorack_size8_class8"
					})
				elif missing_capacity == 192:
					debug_log("Adding missing MK II Cargo Rack (Size 7) - 192 tons")
					this.cargoRacks.append({
						'name': "MK II Cargo Rack (Size 7)",
						'capacity': 192,
						'size': 7,
						'class': 8,
						'item_name': "mk_ii_cargorack_size7_class8"
					})
				elif missing_capacity == 576:  # 384 + 192
					debug_log("Adding missing MK II Cargo Racks - 384 + 192 tons")
					this.cargoRacks.append({
						'name': "MK II Cargo Rack (Size 8)",
						'capacity': 384,
						'size': 8,
						'class': 8,
						'item_name': "mk_ii_cargorack_size8_class8"
					})
					this.cargoRacks.append({
						'name': "MK II Cargo Rack (Size 7)",
						'capacity': 192,
						'size': 7,
						'class': 8,
						'item_name': "mk_ii_cargorack_size7_class8"
					})
		except ValueError:
			debug_log(f"Could not parse cargo capacity: {this.cargoCapacity}")
	
	return cargo_type  # Return the determined cargo type

def parse_cargo_rack(item_name, module_data):
	"""Parse cargo rack information from module data"""
	try:
		debug_log(f"Parsing cargo rack: {item_name}")
		
		# Extract size and class from item name (e.g., "int_cargorack_size3_class5", "int_largecargorack_size8_class1", or MK II variants)
		if 'cargorack' in item_name.lower() or ('mk' in item_name.lower() and 'rack' in item_name.lower()) or ('rack' in item_name.lower() and 'cargo' in item_name.lower()):
			parts = item_name.split('_')
			debug_log(f"Split parts: {parts}")
			
			# Special handling for MK II cargo racks
			if 'mk' in item_name.lower() and 'ii' in item_name.lower():
				debug_log("Detected MK II cargo rack")
				
				# Try to extract size information from the item name
				size = 8  # Default size
				capacity = 384  # Default capacity
				
				# Look for size indicators in the item name
				for part in parts:
					if part.startswith('size'):
						try:
							size = int(part.replace('size', ''))
							# Calculate capacity based on size (Class 8 = 1.5x multiplier)
							base_capacity = 2 ** size
							capacity = int(base_capacity * 1.5)
							debug_log(f"Extracted size {size} for MK II rack, calculated capacity: {capacity}")
							break
						except ValueError:
							pass
				
				# If no size found, try to determine from capacity or item name patterns
				if '192' in item_name or 'size7' in item_name.lower():
					capacity = 192
					size = 7  # Size 7 Class 8 = 128 * 1.5 = 192
					debug_log(f"Detected 192 capacity MK II rack, using size 7")
				elif '384' in item_name or 'size8' in item_name.lower():
					capacity = 384
					size = 8  # Size 8 Class 8 = 256 * 1.5 = 384
					debug_log(f"Detected 384 capacity MK II rack, using size 8")
				
				result = {
					'name': f"MK II Cargo Rack (Size {size})",
					'capacity': capacity,
					'size': size,
					'class': 8,
					'item_name': item_name
				}
				debug_log(f"Successfully parsed MK II cargo rack: {result}")
				return result
			
			# Handle both formats: standard and large
			if len(parts) >= 4:
				# Find the size and class parts
				size_part = None
				class_part = None
				
				for part in parts:
					if part.startswith('size'):
						size_part = part
					elif part.startswith('class'):
						class_part = part
				
				if size_part and class_part:
					size = int(size_part.replace('size', ''))
					class_num = int(class_part.replace('class', ''))
					
					debug_log(f"Extracted size: {size}, class: {class_num}")
					
					# Calculate capacity based on size and class
					base_capacity = 2 ** size  # Size 1=2, Size 2=4, Size 3=8, etc.
					if class_num == 8:
						# Class 8 racks have 1.5x capacity
						capacity = int(base_capacity * 1.5)
					else:
						# Standard class racks
						capacity = base_capacity
					
					debug_log(f"Calculated capacity: {capacity}")
					
					# Create friendly name
					friendly_name = f"Size {size} Class {class_num} Cargo Rack"
					if class_num == 8:
						friendly_name += " (1.5x Capacity)"
					
					result = {
						'name': friendly_name,
						'capacity': capacity,
						'size': size,
						'class': class_num,
						'item_name': item_name
					}
					
					debug_log(f"Successfully parsed cargo rack: {result}")
					return result
				else:
					debug_log(f"Could not find size or class parts in item name")
			else:
				debug_log(f"Not enough parts in item name: {len(parts)} parts")
		else:
			debug_log(f"Item name doesn't contain 'cargorack': {item_name}")
	except Exception as e:
		debug_log(f"Error parsing cargo rack {item_name}: {e}")
		return None
	
	return None

def update_ranks(ranks):
	"""Update rank information from ranks data"""
	# Update trade rank
	if 'Trade' in ranks:
		trade_data = ranks['Trade']
		if isinstance(trade_data, tuple) and len(trade_data) == 2:
			# Format: (rank_level, progress_percentage)
			rank_level = trade_data[0]
			progress = trade_data[1]
			
			# Convert rank level to rank name
			trade_rank_names = {
				0: "Penniless",
				1: "Mostly Penniless", 
				2: "Peddler",
				3: "Dealer",
				4: "Merchant",
				5: "Broker",
				6: "Entrepreneur",
				7: "Tycoon",
				8: "Elite",
				9: "Elite I",
				10: "Elite II",
				11: "Elite III",
				12: "Elite IV",
				13: "Elite V"
			}
			
			this.tradeRank = trade_rank_names.get(rank_level, f"Rank {rank_level}")
			this.tradeProgress = progress
			debug_log(f"Trade rank updated: {this.tradeRank} ({this.tradeProgress}%)")
	
	# Update exploration rank
	if 'Explore' in ranks:
		explore_data = ranks['Explore']
		if isinstance(explore_data, tuple) and len(explore_data) == 2:
			# Format: (rank_level, progress_percentage)
			rank_level = explore_data[0]
			progress = explore_data[1]
			
			# Convert rank level to rank name
			explore_rank_names = {
				0: "Aimless",
				1: "Mostly Aimless",
				2: "Scout",
				3: "Surveyor",
				4: "Trailblazer",
				5: "Pathfinder",
				6: "Ranger",
				7: "Pioneer",
				8: "Elite",
				9: "Elite I",
				10: "Elite II",
				11: "Elite III",
				12: "Elite IV",
				13: "Elite V"
			}
			
			this.explorationRank = explore_rank_names.get(rank_level, f"Rank {rank_level}")
			this.explorationProgress = progress
			debug_log(f"Exploration rank updated: {this.explorationRank} ({this.explorationProgress}%)")

def update_trade_rank(ranks):
	"""Update trade rank information from ranks data (legacy function)"""
	update_ranks(ranks)

def update_credits(credits_amount):
	"""Update credits information"""
	this.credits = credits_amount
	debug_log(f"Credits updated: {this.credits:,}")  # Debug
	# Update budget display when credits change
	if this.budgetEnabled:
		update_budget_display()

def send_discord_webhook(webhook_url, message, embed=None):
	"""Send a message to Discord via webhook"""
	payload = {
		"username": this.webhookBotName
	}
	
	# Add bot avatar if provided
	if this.webhookBotImage and this.webhookBotImage.strip():
		payload["avatar_url"] = this.webhookBotImage.strip()
	
	if embed:
		payload["embeds"] = [embed]
	else:
		payload["content"] = message
	
	try:
		response = requests.post(webhook_url, json=payload)
		response.raise_for_status()
		debug_log(f"Discord webhook sent successfully")
		return True
	except requests.exceptions.RequestException as e:
		debug_log(f"Discord webhook error: {e}")
		return False

def handle_market_sell(entry):
	"""Handle MarketSell journal event"""
	debug_log(f"handle_market_sell called - enableWebhooks: {this.enableWebhooks}, webhookUrl: {this.webhookUrl}")
	if not this.enableWebhooks or not this.webhookUrl:
		debug_log("Webhook disabled or no URL")
		return
		
	cargo_name = entry.get('Type_Localised', entry.get('Type', 'Unknown'))
	# Capitalize first letter of each word in cargo name
	cargo_name = ' '.join(word.capitalize() for word in cargo_name.split())
	quantity = entry.get('Count', 0)
	price_per_unit = entry.get('SellPrice', 0)
	total_price = entry.get('TotalSale', 0)
	
	# Use stored location data
	station = this.currentStation
	system = this.currentSystem
	
	debug_log(f"Location data - Station: {station}, System: {system}")
	debug_log(f"Commander name for webhook: {this.commanderName}")
	
	# Calculate profit if we have purchase history
	buy_price, profit_per_unit, total_profit = calculate_profit(cargo_name, quantity, price_per_unit)
	
	# Create Discord embed
	embed = {
		"title": "🚛 Cargo Sale Completed",
		"color": 0x00ff00,  # Green color for sales
		"author": {
			"name": f"Commander {this.commanderName}",
			"icon_url": "https://cdn.discordapp.com/emojis/1234567890.png"  # You can add a custom icon URL here
		},
		"fields": [
			{
				"name": "📦 Cargo",
				"value": cargo_name,
				"inline": True
			},
			{
				"name": "🔢 Quantity",
				"value": f"{quantity:,} units",
				"inline": True
			},
			{
				"name": "💰 Price per unit",
				"value": f"{price_per_unit:,} cr",
				"inline": True
			},
			{
				"name": "💎 Total sale",
				"value": f"{total_price:,} cr",
				"inline": True
			}
		],
		"footer": {
			"text": "Cargo Manifest Bot"
		},
		"timestamp": datetime.now().isoformat()
	}
	
	# Add thumbnail if avatar URL is provided
	if this.webhookAvatar and this.webhookAvatar.strip():
		embed["thumbnail"] = {
			"url": this.webhookAvatar.strip()
		}
	
	# Add profit information if available
	if buy_price is not None:
		profit_color = 0x00ff00 if total_profit >= 0 else 0xff0000  # Green for profit, red for loss
		profit_emoji = "📈" if total_profit >= 0 else "📉"
		profit_text = "Profit" if total_profit >= 0 else "Loss"
		
		embed["color"] = profit_color
		embed["fields"].append({
			"name": f"{profit_emoji} {profit_text}",
			"value": f"**{total_profit:+,} cr** ({profit_per_unit:+,} cr/unit)",
			"inline": True
		})
		embed["fields"].append({
			"name": "📊 Buy price",
			"value": f"{buy_price:,.0f} cr/unit",
			"inline": True
		})
	
	embed["fields"].append({
		"name": "📍 Location",
		"value": f"{station}, {system}",
		"inline": False
	})
	
	debug_log(f"Sending webhook embed for sale")
	send_discord_webhook(this.webhookUrl, None, embed)

def handle_market_buy(entry):
	"""Handle MarketBuy journal event"""
	debug_log(f"handle_market_buy called - enableWebhooks: {this.enableWebhooks}, webhookUrl: {this.webhookUrl}")
	if not this.enableWebhooks or not this.webhookUrl:
		debug_log("Webhook disabled or no URL")
		return
		
	cargo_name = entry.get('Type_Localised', entry.get('Type', 'Unknown'))
	# Capitalize first letter of each word in cargo name
	cargo_name = ' '.join(word.capitalize() for word in cargo_name.split())
	quantity = entry.get('Count', 0)
	price_per_unit = entry.get('BuyPrice', 0)
	total_price = entry.get('TotalCost', 0)
	
	# Use stored location data
	station = this.currentStation
	system = this.currentSystem
	
	debug_log(f"Location data - Station: {station}, System: {system}")
	
	# Track the purchase for profit calculation
	track_purchase(cargo_name, quantity, price_per_unit, total_price)
	
	# Create Discord embed
	embed = {
		"title": "🛒 Cargo Purchase Completed",
		"color": 0x0099ff,  # Blue color for purchases
		"author": {
			"name": f"Commander {this.commanderName}",
			"icon_url": "https://cdn.discordapp.com/emojis/1234567890.png"  # You can add a custom icon URL here
		},
		"fields": [
			{
				"name": "📦 Cargo",
				"value": cargo_name,
				"inline": True
			},
			{
				"name": "🔢 Quantity",
				"value": f"{quantity:,} units",
				"inline": True
			},
			{
				"name": "💰 Price per unit",
				"value": f"{price_per_unit:,} cr",
				"inline": True
			},
			{
				"name": "💸 Total cost",
				"value": f"{total_price:,} cr",
				"inline": True
			},
			{
				"name": "📍 Location",
				"value": f"{station}, {system}",
				"inline": False
			}
		],
		"footer": {
			"text": "Cargo Manifest Bot"
		},
		"timestamp": datetime.now().isoformat()
	}
	
	# Add thumbnail if avatar URL is provided
	if this.webhookAvatar and this.webhookAvatar.strip():
		embed["thumbnail"] = {
			"url": this.webhookAvatar.strip()
		}
	
	debug_log(f"Sending webhook embed for purchase")
	send_discord_webhook(this.webhookUrl, None, embed)

def track_purchase(cargo_name, quantity, price_per_unit, total_cost):
	"""Track a cargo purchase for profit calculation"""
	if cargo_name not in this.purchaseHistory:
		this.purchaseHistory[cargo_name] = {
			'quantity': 0,
			'total_cost': 0,
			'avg_price': 0
		}
	
	# Update purchase history
	current = this.purchaseHistory[cargo_name]
	current['quantity'] += quantity
	current['total_cost'] += total_cost
	current['avg_price'] = current['total_cost'] / current['quantity']
	
	debug_log(f"Tracked purchase: {cargo_name} x{quantity} at {price_per_unit} cr/unit (avg: {current['avg_price']:.2f} cr/unit)")
	
	# Update display to show current trade status
	update_display()

def calculate_profit(cargo_name, sell_quantity, sell_price_per_unit):
	"""Calculate profit/loss for a cargo sale"""
	if cargo_name not in this.purchaseHistory:
		return None, None, None  # No purchase history
	
	purchase_data = this.purchaseHistory[cargo_name]
	buy_price_per_unit = purchase_data['avg_price']
	
	# Calculate profit per unit and total profit
	profit_per_unit = sell_price_per_unit - buy_price_per_unit
	total_profit = profit_per_unit * sell_quantity
	
	# Add to total trade profit
	this.totalTradeProfit += total_profit
	
	# Update remaining quantity
	purchase_data['quantity'] -= sell_quantity
	if purchase_data['quantity'] <= 0:
		# All sold, remove from history
		del this.purchaseHistory[cargo_name]
		debug_log(f"Removed {cargo_name} from purchase history (all sold)")
	else:
		# Recalculate average price for remaining quantity
		purchase_data['total_cost'] = purchase_data['quantity'] * purchase_data['avg_price']
		debug_log(f"Updated {cargo_name} quantity: {purchase_data['quantity']} remaining")
	
	# Update display to show updated trade status
	update_display()
	
	# Update Discord status when trade profit changes
	if this.enableDiscordRPC:
		update_discord_status()
	
	return buy_price_per_unit, profit_per_unit, total_profit

def update_captain_info_display():
    if not hasattr(this, 'captainInfoLabel'):
        return  # UI not initialized yet
    lines = []
    # Credits
    try:
        showCredits = config.get_bool("cm_showCredits")
    except:
        showCredits = True
    if showCredits and this.credits > 0:
        lines.append("💰 Credits: {:,}".format(this.credits))
    # Trade Rank
    try:
        showTradeRank = config.get_bool("cm_showTradeRank")
    except:
        showTradeRank = True
    if showTradeRank and this.tradeRank != "None":
        lines.append(" Trade Rank: {rank} ({progress}%)".format(
            rank=this.tradeRank, progress=this.tradeProgress))
    if not lines:
        lines.append("No captain information available.")
    this.captainInfoLabel["text"] = "\n".join(lines)


def update_cargo_manifest_display():
    if not hasattr(this, 'cargoManifestLabel'):
        return  # UI not initialized yet
    
    debug_log(f"Cargo manifest display - Type: {this.cargoType}, Capacity: {this.cargoCapacity}, Inventory: {len(this.inventory) if this.inventory else 0} items")
    
    lines = []
    lines.append("   {type} Manifest ({curr}/{cap})".format(
        type=this.cargoType, curr=this.inventory and sum(int(i['Count']) for i in this.inventory) or 0, cap=this.cargoCapacity))
    
    # Total Trade Profit
    profit_text = "Total Trade Profit" if this.totalTradeProfit > 0 else "Total Trade Loss" if this.totalTradeProfit < 0 else "Total Trade Profit"
    lines.append(f"   {profit_text}: {this.totalTradeProfit:+,}")
    cargo_items = []
    for i in this.inventory:
        line = ""
        if i['Name'] in this.items:
            line = "{quant} {name}".format(quant=i['Count'], name=this.items[i['Name']]['name'])
        else:
            line = "{quant} {name}".format(quant=i['Count'], name=(i['Name_Localised'] if 'Name_Localised' in i else i['Name']))
        if 'Stolen' in i and i['Stolen'] > 0:
            line = line+", {} stolen".format(i['Stolen'])
        if 'MissionID' in i:
            line = line+" (Mission)"
        cargo_items.append(line)
    if this.inventory == []:
        for i in this.cargoDict:
            line = "{quant} {name}".format(name=(this.items[i]['name'] if i in this.items else i), quant=this.cargoDict[i])
            cargo_items.append(line)
    
    lines.append("      Cargo Items:")
    if cargo_items:
        for item in cargo_items:
            lines.append("                          " + item)
    else:
        lines.append("                          Empty")
    this.cargoManifestLabel["text"] = "\n".join(lines)


def update_budget_display():
	# Update the budget display
	if not hasattr(this, 'budgetLabel'):
		return  # UI not initialized yet
	
	current_credits = getattr(this, 'credits', 0)  # Use 0 if credits not loaded yet
	debug_log(f"Budget display - Credits: {current_credits:,}, Goal: {this.budgetGoal:,}, Enabled: {this.budgetEnabled}")
	
	budget_text = ""
	
	if not this.budgetEnabled:
		budget_text = "💳 Budget tracking is disabled.\n\nEnable it in the settings to track your credit goals."
	else:
		budget_text += f"💳 Budget Tracking\n\n"
		
		if this.budgetGoal > 0:
			# Calculate progress
			current_credits = getattr(this, 'credits', 0)  # Use 0 if credits not loaded yet
			remaining = this.budgetGoal - current_credits
			progress_percent = (current_credits / this.budgetGoal) * 100 if this.budgetGoal > 0 else 0
			
			budget_text += f"🎯 Credit Goal: {this.budgetGoal:,}\n"
			budget_text += f"💰 Current Credits: {current_credits:,}\n"
			budget_text += f"📊 Progress: {progress_percent:.1f}%\n\n"
			
			if remaining > 0:
				budget_text += f"📈 Still needed: {remaining:,} credits"
			elif remaining < 0:
				budget_text += f"🎉 Goal exceeded by: {abs(remaining):,} credits!"
			else:
				budget_text += f"🎉 Goal reached exactly!"
		else:
			budget_text += "🎯 Set a credit goal in the settings to start tracking your progress."
	
	this.budgetLabel.config(text=budget_text)


def update_cargo_racks_display():
	# Update the cargo racks display
	if not hasattr(this, 'cargoRacksLabel'):
		return  # UI not initialized yet
	
	debug_log(f"Cargo racks display - Found {len(this.cargoRacks)} cargo racks")
	
	racks_text = ""
	
	if not this.cargoRacks:
		racks_text = "📦 No cargo racks detected.\n\nCheck your ship's loadout to see equipped cargo racks."
	else:
		racks_text += f"📦 Cargo Racks ({len(this.cargoRacks)} equipped)\n\n"
		
		# Sort racks by size and class for better display
		sorted_racks = sorted(this.cargoRacks, key=lambda x: (x['size'], x['class']))
		
		total_capacity = 0
		for i, rack in enumerate(sorted_racks, 1):
			racks_text += f"{i}. {rack['name']}\n"
			racks_text += f"   Capacity: {rack['capacity']} tons\n"
			total_capacity += rack['capacity']
			
			# Add separator between racks
			if i < len(sorted_racks):
				racks_text += "\n"
		
		racks_text += f"\n📊 Total Cargo Capacity: {total_capacity} tons"
	
	this.cargoRacksLabel.config(text=racks_text)

def handle_community_goal(entry):
	"""Handle CommunityGoal journal event"""
	debug_log(f"Processing community goal: {entry}")
	debug_log(f"Community goal keys: {list(entry.keys())}")
	
	# Check if the entry contains CurrentGoals array
	if 'CurrentGoals' in entry and isinstance(entry['CurrentGoals'], list):
		debug_log(f"Found CurrentGoals array with {len(entry['CurrentGoals'])} goals")
		
		for goal in entry['CurrentGoals']:
			debug_log(f"Processing individual goal: {goal}")
			debug_log(f"Individual goal keys: {list(goal.keys())}")
			
			# Extract data from the individual goal object
			goal_id = goal.get('CGID', 0)
			goal_name = goal.get('Title', 'Unknown Goal')
			goal_system = goal.get('SystemName', 'Unknown System')
			goal_station = goal.get('MarketName', 'Unknown Station')
			goal_end_date = goal.get('Expiry', 'Unknown')
			
			# Get player's contribution and rank
			player_contribution = goal.get('PlayerContribution', 0)
			player_percent = goal.get('PlayerPercentileBand', 0)
			player_rank = 0  # Not provided in this format
			
			# Get global contribution
			global_contribution = goal.get('CurrentTotal', 0)
			
			# Get tier information
			tier_reached = goal.get('TierReached', '')
			top_tier = goal.get('TopTier', {})
			tier_name = top_tier.get('Name', '') if isinstance(top_tier, dict) else ''
			
			debug_log(f"Parsed goal data - ID: {goal_id}, Name: {goal_name}, System: {goal_system}, Station: {goal_station}")
			debug_log(f"Player data - Contribution: {player_contribution}, Percent: {player_percent}, Tier: {tier_reached}")
			
			# Store community goal data
			goal_data = {
				'id': goal_id,
				'name': goal_name,
				'description': '',  # Not provided in this format
				'system': goal_system,
				'station': goal_station,
				'end_date': goal_end_date,
				'player_contribution': player_contribution,
				'player_percent': player_percent,
				'player_rank': player_rank,
				'global_contribution': global_contribution,
				'tier': tier_reached,
				'target_tier': tier_name,
				'is_from_game': True
			}
			
			# Update or add to community goals list
			found = False
			for i, existing_goal in enumerate(this.communityGoals):
				if existing_goal['id'] == goal_id:
					this.communityGoals[i] = goal_data
					found = True
					debug_log(f"Updated existing community goal: {goal_name}")
					break
			
			if not found:
				this.communityGoals.append(goal_data)
				debug_log(f"Added new community goal: {goal_name}")
		
		# Update display
		update_community_goals_display()
		debug_log(f"Community goals updated from CurrentGoals array")
	else:
		# Fallback to old format
		debug_log("No CurrentGoals array found, using fallback parsing")
		
		# Try different possible field names for community goal data
		goal_id = entry.get('CGID', entry.get('CommunityGoalID', entry.get('ID', 0)))
		goal_name = entry.get('Name', entry.get('CommunityGoalName', entry.get('Title', 'Unknown Goal')))
		goal_description = entry.get('Description', entry.get('Objective', ''))
		goal_system = entry.get('SystemName', entry.get('System', 'Unknown System'))
		goal_station = entry.get('StationName', entry.get('Station', 'Unknown Station'))
		goal_end_date = entry.get('EndDate', entry.get('ExpiryDate', 'Unknown'))
		
		# Get player's contribution and rank - try multiple field names
		player_contribution = entry.get('PlayerContribution', entry.get('Contribution', entry.get('Units', 0)))
		player_percent = entry.get('PlayerPercentileBand', entry.get('Percentile', entry.get('RankPercent', 0)))
		player_rank = entry.get('PlayerRank', entry.get('Rank', entry.get('Position', 0)))
		
		# Also check for tier information
		tier = entry.get('Tier', entry.get('CurrentTier', 0))
		target_tier = entry.get('TargetTier', entry.get('MaxTier', 0))
		
		debug_log(f"Parsed goal data - ID: {goal_id}, Name: {goal_name}, System: {goal_system}, Station: {goal_station}")
		debug_log(f"Player data - Contribution: {player_contribution}, Rank: {player_rank}, Percent: {player_percent}")
		
		# Store community goal data
		goal_data = {
			'id': goal_id,
			'name': goal_name,
			'description': goal_description,
			'system': goal_system,
			'station': goal_station,
			'end_date': goal_end_date,
			'player_contribution': player_contribution,
			'player_percent': player_percent,
			'player_rank': player_rank,
			'tier': tier,
			'target_tier': target_tier,
			'is_from_game': True
		}
		
		# Update or add to community goals list
		found = False
		for i, existing_goal in enumerate(this.communityGoals):
			if existing_goal['id'] == goal_id:
				this.communityGoals[i] = goal_data
				found = True
				debug_log(f"Updated existing community goal: {goal_name}")
				break
		
		if not found:
			this.communityGoals.append(goal_data)
			debug_log(f"Added new community goal: {goal_name}")
		
		# Update display
		update_community_goals_display()
		debug_log(f"Community goal updated: {goal_name}")

def load_community_goals_from_edmc():
	"""Load community goals from EDMC state"""
	debug_log("Loading community goals from EDMC state")
	
	try:
		# Try to get community goals from EDMC's state
		from config import config
		
		# Check if EDMC has community goals data
		edmc_community_goals = config.get('communitygoals', [])
		if edmc_community_goals:
			debug_log(f"Found {len(edmc_community_goals)} community goals in EDMC state")
			
			for goal in edmc_community_goals:
				goal_data = {
					'id': goal.get('id', 0),
					'name': goal.get('name', 'Unknown Goal'),
					'description': goal.get('description', ''),
					'system': goal.get('system', 'Unknown System'),
					'station': goal.get('station', 'Unknown Station'),
					'end_date': goal.get('endDate', 'Unknown'),
					'player_contribution': goal.get('contribution', 0),
					'player_percent': goal.get('percentile', 0),
					'player_rank': goal.get('rank', 0),
					'is_edmc': True
				}
				
				this.communityGoals.append(goal_data)
				debug_log(f"Added EDMC community goal: {goal_data['name']}")
			
			# Update display
			update_community_goals_display()
		else:
			debug_log("No community goals found in EDMC state")
			
	except Exception as e:
		debug_log(f"Error loading community goals from EDMC: {e}")
		# Fallback to external API if EDMC doesn't have data
		fetch_community_goals_fallback()

def fetch_community_goals_fallback():
	"""Fallback to fetch community goals from external APIs if EDMC doesn't have data"""
	debug_log("Using fallback to external API for community goals")
	
	try:
		import requests
		import threading
		
		def fetch_inara_goals():
			try:
				url = "https://inara.cz/api/v1/communitygoals"
				response = requests.get(url, timeout=10)
				if response.status_code == 200:
					data = response.json()
					if 'communityGoals' in data:
						goals = data['communityGoals']
						debug_log(f"Fetched {len(goals)} community goals from Inara")
						
						# Process and store community goals
						for goal in goals:
							if goal.get('isActive', False):
								goal_data = {
									'id': goal.get('communitygoalGameID', 0),
									'name': goal.get('communitygoalName', 'Unknown Goal'),
									'description': goal.get('communitygoalDescription', ''),
									'system': goal.get('starsystemName', 'Unknown System'),
									'station': goal.get('stationName', 'Unknown Station'),
									'end_date': goal.get('endDate', 'Unknown'),
									'player_contribution': 0,  # Will be updated from game events
									'player_percent': 0,
									'player_rank': 0,
									'is_external': True
								}
								
								# Add to community goals list if not already present
								found = False
								for existing_goal in this.communityGoals:
									if existing_goal['id'] == goal_data['id']:
										found = True
										break
								
								if not found:
									this.communityGoals.append(goal_data)
									debug_log(f"Added community goal: {goal_data['name']}")
						
						# Update display
						update_community_goals_display()
					else:
						debug_log("No community goals found in Inara response")
				else:
					debug_log(f"Inara API request failed with status {response.status_code}")
			except Exception as e:
				debug_log(f"Error fetching community goals from Inara: {e}")
		
		# Run the fetch in a background thread to avoid blocking startup
		fetch_thread = threading.Thread(target=fetch_inara_goals, daemon=True)
		fetch_thread.start()
		
	except Exception as e:
		debug_log(f"Error setting up community goals fallback: {e}")

def check_state_for_community_goals(state):
	"""Check for community goals in the game state"""
	debug_log("Checking state for community goals")
	debug_log(f"State keys: {list(state.keys())}")
	
	# Look for community goal related keys in state
	community_goal_keys = [key for key in state.keys() if 'community' in key.lower() or 'goal' in key.lower()]
	debug_log(f"Potential community goal keys: {community_goal_keys}")
	
	for key in community_goal_keys:
		debug_log(f"Community goal key '{key}': {state[key]}")
	
	# Check if there are any community goals in the state
	if 'CommunityGoals' in state:
		debug_log(f"Found CommunityGoals in state: {state['CommunityGoals']}")
		for goal in state['CommunityGoals']:
			handle_community_goal(goal)
	elif 'communitygoals' in state:
		debug_log(f"Found communitygoals in state: {state['communitygoals']}")
		for goal in state['communitygoals']:
			handle_community_goal(goal)

def update_community_goals_display():
	"""Update the community goals display"""
	debug_log("Updating community goals display")
	
	if not hasattr(this, 'communityGoalsLabel'):
		return  # UI not initialized yet
	
	debug_log(f"Number of community goals: {len(this.communityGoals)}")
	for i, goal in enumerate(this.communityGoals):
		debug_log(f"Goal {i+1}: {goal}")
	
	goals_text = "🎯 Community Goals\n\n"
	
	debug_log(f"Building goals text. Number of goals: {len(this.communityGoals)}")
	
	if not this.communityGoals:
		goals_text += "No active community goals found.\n"
		goals_text += "Check the mission board for available community goals."
	else:
		debug_log(f"Processing {len(this.communityGoals)} goals for display")
		for i, goal in enumerate(this.communityGoals, 1):
			debug_log(f"Processing goal {i}: {goal['name']}")
			try:
				goals_text += f"🎯 {goal['name']}\n"
				debug_log("Added goal name")
				goals_text += f"📍 Location: {goal['station']}, {goal['system']}\n"
				debug_log("Added location")
				goals_text += f"📅 End Date: {goal['end_date']}\n"
				debug_log("Added end date")
				
				# Show tier information if available
				if goal.get('tier'):
					goals_text += f"🏆 Current Tier: {goal['tier']}"
					if goal.get('target_tier'):
						goals_text += f" / {goal['target_tier']}"
					goals_text += "\n"
					debug_log("Added tier info")
				
				# Show global contribution if available
				if goal.get('global_contribution', 0) > 0:
					goals_text += f"🌍 Global Contribution: {goal['global_contribution']:,}\n"
					debug_log("Added global contribution info")
				
				# Show player contribution if available
				if goal.get('player_contribution', 0) > 0:
					goals_text += f"📊 Your Contribution: {goal['player_contribution']:,}\n"
					goals_text += f"🏆 Your Rank: Top {goal['player_percent']}%\n"
					debug_log("Added player contribution info")
				else:
					goals_text += f"📊 Your Contribution: Not participating\n"
					debug_log("Added not participating message")
				
				if goal['description']:
					goals_text += f"📝 Description: {goal['description']}\n"
					debug_log("Added description")
				
				# Indicate data source
				if goal.get('is_from_game', False):
					##goals_text += f"🎮 Data from game events\n"
					debug_log("Added game events source")
				elif goal.get('is_edmc', False):
					goals_text += f"📡 Data from EDMC\n"
					debug_log("Added EDMC source")
				elif goal.get('is_external', False):
					goals_text += f"🌐 Data from external API\n"
					debug_log("Added external API source")
				
				goals_text += "\n"
				debug_log("Finished processing goal")
			except Exception as e:
				debug_log(f"Error processing goal: {e}")
				import traceback
				debug_log(f"Traceback: {traceback.format_exc()}")
	
	# Update the label
	debug_log(f"About to update label with text length: {len(goals_text)}")
	this.communityGoalsLabel.config(text=goals_text)
	debug_log(f"Community goals display updated with text: {goals_text[:200]}...")
	
	# Force update the display
	this.communityGoalsLabel.update()

def update_display():
	# Update both sections so switching is always instant
	update_captain_info_display()
	update_cargo_manifest_display()
	update_budget_display()
	update_cargo_racks_display()
	update_community_goals_display()
	# No need to set manifest or title here
	# Frame switching is handled by the combobox
	pass

def init_discord_rpc():
	"""Initialize Discord Status Updates"""
	if not this.enableDiscordRPC:
		return
	
	debug_log("Discord Status Updates initialized")
	# No longer start background thread - status updates will be event-driven

def discord_status_update_loop():
	"""Background thread to update Discord status via webhook - DEPRECATED"""
	# This function is no longer used - status updates are now event-driven
	debug_log("Discord status update loop is deprecated - using event-driven updates")

def update_discord_status():
	"""Update Discord status with current game state via webhook"""
	# Use status webhook if available, otherwise fall back to main webhook
	webhook_url = this.discordStatusWebhook if this.discordStatusWebhook else this.webhookUrl
	if not this.enableDiscordRPC or not webhook_url:
		return
	
	# Debug logging for status update
	debug_log(f"Status update - Commander: {this.commanderName}, System: {this.currentSystem}, Station: {this.currentStation}")
	
	try:
		# Determine current activity based on station presence and cargo
		cargo_count = 0
		if this.inventory:
			cargo_count = sum(int(i['Count']) for i in this.inventory)
		
		if this.currentStation != "Unknown":
			# At a station - could be trading or just docked
			if cargo_count > 0:
				activity = "Trading"
				details = f"At {this.currentStation}"
			else:
				activity = "Docked"
				details = f"At {this.currentStation}"
			state = f"System: {this.currentSystem}"
		else:
			# Not at a station - exploring or traveling
			if cargo_count > 0:
				activity = "Transporting"
				details = f"In {this.currentSystem}"
				state = "Traveling with cargo"
			else:
				activity = "Exploring"
				details = f"In {this.currentSystem}"
				state = "Traveling through space"
		
		# Add captain name
		captain_info = f"Commander {this.commanderName}" if this.commanderName != "Unknown" else "Unknown Commander"
		
		# Add cargo info if available
		if cargo_count > 0:
			state += f" | Cargo: {cargo_count}/{this.cargoCapacity}"
		
		# Add trade profit if available
		if this.totalTradeProfit != 0:
			profit_text = f"Profit: {this.totalTradeProfit:+,}" if this.totalTradeProfit > 0 else f"Loss: {this.totalTradeProfit:+,}"
			state += f" | {profit_text}"
		
		# Add appropriate rank based on activity
		if activity == "Trading" and this.tradeRank != "None":
			state += f" | {this.tradeRank} ({this.tradeProgress}%)"
		elif activity == "Exploring" and this.explorationRank != "None":
			state += f" | {this.explorationRank} ({this.explorationProgress}%)"
		elif activity == "Transporting" and this.tradeRank != "None":
			state += f" | {this.tradeRank} ({this.tradeProgress}%)"
		
		# Create status embed with appropriate colors for each activity
		activity_colors = {
			"Trading": 0x00ff00,      # Green for trading
			"Docked": 0xffff00,       # Yellow for docked
			"Transporting": 0xff6600,  # Orange for transporting cargo
			"Exploring": 0x0099ff      # Blue for exploring
		}
		
		embed = {
			"title": f"🎮 {activity}",
			"description": f"**{captain_info}**\n{details}\n{state}",
			"color": activity_colors.get(activity, 0x0099ff),  # Default to blue
			"footer": {
				"text": "Elite Dangerous - Cargo Manifest Remastered"
			},
			"timestamp": datetime.now().isoformat()
		}
		
		# Send status update via webhook
		send_discord_webhook(webhook_url, None, embed)
		
		# Update last status update timestamp for debugging
		this.lastStatusUpdate = time.time()
		debug_log(f"Status update sent successfully")
		
	except Exception as e:
		debug_log(f"Error updating Discord status: {e}")

def cleanup_discord_rpc():
	"""Clean up Discord status updates on plugin shutdown"""
	debug_log("Discord Status Updates cleaned up")
	# No thread to clean up since we're using event-driven updates