#!/bin/bash
# =============================================================================
# Setup: Cmd+Option+Ctrl+K hotkey to run macOS kill-all script
# =============================================================================
# This script creates a macOS Automator Quick Action (Service) and binds it
# to the keyboard shortcut: Cmd + Option + Ctrl + K
#
# Usage: bash setup-killall-hotkey.sh
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KILLALL_SCRIPT="$SCRIPT_DIR/macOS-killall-scripts.sh"
SERVICE_NAME="KillAllApps"
WORKFLOW_DIR="$HOME/Library/Services/${SERVICE_NAME}.workflow"

# Ensure the killall script exists and is executable
if [ ! -f "$KILLALL_SCRIPT" ]; then
    echo "Error: macOS-killall-scripts.sh not found in $SCRIPT_DIR"
    exit 1
fi
chmod +x "$KILLALL_SCRIPT"

echo "Creating Automator Quick Action..."

# Create the workflow directory structure
mkdir -p "$WORKFLOW_DIR/Contents"

# Create the Info.plist
cat > "$WORKFLOW_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>KillAllApps</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
		</dict>
	</array>
</dict>
</plist>
PLIST

# Create the workflow document
cat > "$WORKFLOW_DIR/Contents/document.wflow" << WFLOW
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>523</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<integer>2</integer>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<true/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>2.0.3</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMLargeIconName</key>
				<string>RunShellScriptAction</string>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key>
					<dict/>
					<key>CheckedForUserDefaultShell</key>
					<dict/>
					<key>inputMethod</key>
					<dict/>
					<key>shell</key>
					<dict/>
					<key>source</key>
					<dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
					<string>source "$KILLALL_SCRIPT" &amp;&amp; force_kill_all_apps</string>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/bash</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript-MY</string>
				<key>CFBundleVersion</key>
				<string>2.0.3</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Category</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>$(uuidgen)</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>OutputUUID</key>
				<string>$(uuidgen)</string>
				<key>UUID</key>
				<string>$(uuidgen)</string>
				<key>UnlocalizedApplications</key>
				<array>
					<string>Automator</string>
				</array>
				<key>arguments</key>
				<dict>
					<key>0</key>
					<dict>
						<key>default value</key>
						<string>echo "Hello World"</string>
						<key>name</key>
						<string>COMMAND_STRING</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
					</dict>
					<key>1</key>
					<dict>
						<key>default value</key>
						<string>/bin/sh</string>
						<key>name</key>
						<string>shell</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
					</dict>
					<key>2</key>
					<dict>
						<key>default value</key>
						<integer>0</integer>
						<key>name</key>
						<string>inputMethod</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
					</dict>
				</dict>
			</dict>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
WFLOW

echo "Quick Action '$SERVICE_NAME' created at: $WORKFLOW_DIR"

# Assign keyboard shortcut: Cmd+Option+Ctrl+K
# @ = Cmd, ~ = Option, ^ = Ctrl
echo "Assigning keyboard shortcut: Cmd+Option+Ctrl+K..."
defaults write pbs NSServicesStatus -dict-add \
    "\"(null) - ${SERVICE_NAME} - runWorkflowAsService\"" \
    '{ "enabled" = 1; "key_equivalent" = "@~^k"; }'

echo ""
echo "============================================="
echo "  Setup complete!"
echo "============================================="
echo ""
echo "  Shortcut: Cmd + Option + Ctrl + K"
echo "  Action:   Force quit all non-essential apps"
echo ""
echo "  If the shortcut doesn't work immediately:"
echo "  1. Go to System Settings > Keyboard > Keyboard Shortcuts > Services"
echo "  2. Find '$SERVICE_NAME' under 'General'"
echo "  3. Enable it and set shortcut to: Cmd+Option+Ctrl+K"
echo ""
echo "  To change which function runs, edit the workflow at:"
echo "  $WORKFLOW_DIR/Contents/document.wflow"
echo "  (Look for the COMMAND_STRING and change 'force_kill_all_apps'"
echo "   to any function from macOS-killall-scripts.sh)"
echo "============================================="
