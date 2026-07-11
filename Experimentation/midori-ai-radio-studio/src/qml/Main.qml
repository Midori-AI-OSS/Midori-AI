import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.kirigami as Kirigami
import org.midoriai.radio

Kirigami.ApplicationWindow {
    id: root
    width: 1440
    height: 900
    minimumWidth: 1050
    minimumHeight: 680
    title: "Midori AI Radio Studio"

    property var songs: []
    property var channels: []
    property var downloads: []
    property var selectedSong: null
    property var promptStore: ({ version: 0, prompts: ({}) })
    property var feedbackEntries: []
    property var environment: ({})
    property bool busy: false
    property string statusText: "Ready"
    property string selectedPromptKey: "comment"

    RadioBackend { id: backend }

    function parseResult(raw) {
        try {
            return JSON.parse(raw)
        } catch (error) {
            return { ok: false, message: "The backend returned invalid JSON: " + error, data: null }
        }
    }

    function runResult(raw, onSuccess) {
        const result = parseResult(raw)
        statusText = result.message || ""
        if (!result.ok) {
            errorBanner.text = result.message || "Unknown error"
            errorBanner.visible = true
            return null
        }
        errorBanner.visible = false
        if (onSuccess)
            onSuccess(result.data)
        return result.data
    }

    function loadSettings() {
        runResult(backend.loadSettings(), function(data) {
            libraryRoot.text = data.libraryRoot || ""
            downloadsRoot.text = data.downloadsDir || ""
            modelField.text = data.model || ""
            variantField.text = data.variant || ""
            fallbackModelField.text = data.fallbackModel || ""
            fallbackVariantField.text = data.fallbackVariant || ""
            includeBlocked.checked = !!data.includeBlocked
        })
    }

    function saveSettings() {
        const payload = {
            libraryRoot: libraryRoot.text.trim(),
            downloadsDir: downloadsRoot.text.trim(),
            model: modelField.text.trim(),
            variant: variantField.text.trim(),
            fallbackModel: fallbackModelField.text.trim(),
            fallbackVariant: fallbackVariantField.text.trim(),
            includeBlocked: includeBlocked.checked
        }
        runResult(backend.saveSettings(JSON.stringify(payload)))
    }

    function refreshLibrary() {
        busy = true
        saveSettings()
        const songResult = parseResult(backend.scanLibrary(libraryRoot.text.trim(), includeBlocked.checked))
        const channelResult = parseResult(backend.scanChannels(libraryRoot.text.trim()))
        busy = false
        if (!songResult.ok) {
            runResult(JSON.stringify(songResult))
            return
        }
        songs = songResult.data || []
        if (channelResult.ok)
            channels = channelResult.data || []
        statusText = songResult.message
        selectedSong = null
        songList.currentIndex = -1
    }

    function refreshDownloads() {
        runResult(backend.recentDownloads(libraryRoot.text.trim(), downloadsRoot.text.trim()), function(data) {
            downloads = data || []
        })
    }

    function refreshPromptState() {
        runResult(backend.loadPromptState(), function(data) {
            promptStore = data.store || ({ version: 0, prompts: ({}) })
            feedbackEntries = data.feedback || []
            promptEditor.text = (promptStore.prompts || {})[selectedPromptKey] || ""
            promptVersion.text = "Prompt set v" + (promptStore.version || 0)
        })
    }

    function refreshEnvironment() {
        runResult(backend.environmentStatus(), function(data) { environment = data || ({}) })
    }

    function chooseSong(song) {
        selectedSong = song
        titleField.text = song.title || ""
        artistField.text = song.artist || ""
        albumField.text = song.album || ""
        genreField.text = song.genre || ""
        commentField.text = song.comment || ""
        whyMadeField.text = song.whyMade || ""
        backstoryField.text = song.backstory || ""
        radioReasonField.text = song.radioReason || ""
        musicThemeField.text = song.musicTheme || ""
        takeawayField.text = song.listenerTakeaway || ""
        promptSongLabel.text = song.title || song.fileName || "Selected song"
    }

    function filteredSongs() {
        const needle = searchField.text.trim().toLowerCase()
        const channelNeedle = channelFilter.currentValue || ""
        return songs.filter(function(song) {
            if (!includeBlocked.checked && song.blockedChannel)
                return false
            if (staleOnly.checked && !song.staleComment)
                return false
            if (channelNeedle && song.channel !== channelNeedle)
                return false
            return !needle || (song.searchText || "").indexOf(needle) >= 0
        })
    }

    function feedbackForPrompt() {
        return feedbackEntries.filter(function(entry) { return entry.promptKey === selectedPromptKey }).reverse()
    }

    Component.onCompleted: {
        loadSettings()
        refreshEnvironment()
        refreshPromptState()
    }

    FolderDialog {
        id: libraryFolderDialog
        title: "Choose the Midori AI Radio library folder"
        onAccepted: libraryRoot.text = selectedFolder.toString().replace(/^file:\/\//, "")
    }

    FolderDialog {
        id: downloadsFolderDialog
        title: "Choose the Downloads folder"
        onAccepted: downloadsRoot.text = selectedFolder.toString().replace(/^file:\/\//, "")
    }

    FileDialog {
        id: importDialog
        title: "Choose MP3 files to import"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["MP3 audio (*.mp3)"]
        onAccepted: {
            const sourcePaths = selectedFiles.map(function(url) { return url.toString().replace(/^file:\/\//, "") })
            const payload = {
                root: libraryRoot.text.trim(),
                channel: importChannel.currentText,
                sources: sourcePaths
            }
            runResult(backend.importSongs(JSON.stringify(payload)), function() {
                refreshLibrary()
                refreshDownloads()
            })
        }
    }

    header: QQC2.ToolBar {
        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Heading {
                text: "Midori AI Radio Studio"
                level: 2
                Layout.leftMargin: Kirigami.Units.largeSpacing
            }

            QQC2.Label {
                text: promptVersion.text
                opacity: 0.65
                Layout.leftMargin: Kirigami.Units.largeSpacing
            }

            Item { Layout.fillWidth: true }

            QQC2.BusyIndicator {
                running: busy
                visible: busy
            }

            QQC2.Label {
                text: statusText
                elide: Text.ElideRight
                Layout.maximumWidth: 420
            }

            QQC2.Button {
                text: "Refresh Library"
                icon.name: "view-refresh"
                enabled: !busy
                onClicked: refreshLibrary()
            }

            QQC2.ToolButton {
                text: "Settings"
                icon.name: "settings-configure"
                onClicked: settingsDrawer.open()
            }
        }
    }

    Kirigami.InlineMessage {
        id: errorBanner
        type: Kirigami.MessageType.Error
        visible: false
        showCloseButton: true
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        z: 100
    }

    QQC2.Drawer {
        id: settingsDrawer
        edge: Qt.RightEdge
        width: Math.min(root.width * 0.46, 620)
        height: root.height
        modal: true

        ScrollView {
            anchors.fill: parent
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.largeSpacing
                padding: Kirigami.Units.largeSpacing

                Kirigami.Heading { text: "Studio settings"; level: 2 }

                QQC2.Label { text: "Midori AI Radio library"; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField { id: libraryRoot; Layout.fillWidth: true; placeholderText: "/home/riley/Music/Midori AI Radio" }
                    QQC2.Button { text: "Browse"; onClicked: libraryFolderDialog.open() }
                }

                QQC2.Label { text: "Downloads folder"; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    QQC2.TextField { id: downloadsRoot; Layout.fillWidth: true }
                    QQC2.Button { text: "Browse"; onClicked: downloadsFolderDialog.open() }
                }

                QQC2.CheckBox { id: includeBlocked; text: "Show blocked channels in the library" }

                Kirigami.Separator { Layout.fillWidth: true }
                Kirigami.Heading { text: "OpenCode models"; level: 3 }

                QQC2.Label { text: "Primary model" }
                QQC2.TextField { id: modelField; Layout.fillWidth: true }
                QQC2.Label { text: "Primary variant" }
                QQC2.TextField { id: variantField; Layout.fillWidth: true }
                QQC2.Label { text: "Fallback model" }
                QQC2.TextField { id: fallbackModelField; Layout.fillWidth: true }
                QQC2.Label { text: "Fallback variant" }
                QQC2.TextField { id: fallbackVariantField; Layout.fillWidth: true }

                Kirigami.Separator { Layout.fillWidth: true }
                Kirigami.Heading { text: "Environment"; level: 3 }

                Repeater {
                    model: [
                        ["ffmpeg", environment.ffmpeg],
                        ["ffprobe", environment.ffprobe],
                        ["OpenCode", environment.opencode],
                        ["mpv", environment.mpv],
                        ["KDE Trash", environment.kioTrash]
                    ]
                    delegate: RowLayout {
                        QQC2.Label { text: modelData[1] ? "Available" : "Missing"; color: modelData[1] ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor }
                        QQC2.Label { text: modelData[0]; Layout.fillWidth: true }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    QQC2.Button {
                        text: "Save"
                        highlighted: true
                        onClicked: {
                            saveSettings()
                            refreshEnvironment()
                            settingsDrawer.close()
                        }
                    }
                }
            }
        }
    }

    QQC2.TabBar {
        id: tabBar
        width: parent.width
        QQC2.TabButton { text: "Library"; icon.name: "media-optical-audio" }
        QQC2.TabButton { text: "Import"; icon.name: "document-import" }
        QQC2.TabButton { text: "Channels"; icon.name: "folder-music" }
        QQC2.TabButton { text: "Prompt Lab"; icon.name: "tools-wizard" }
    }

    StackLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: tabBar.bottom
        anchors.bottom: parent.bottom
        currentIndex: tabBar.currentIndex

        Item {
            SplitView {
                anchors.fill: parent
                orientation: Qt.Horizontal

                Kirigami.Card {
                    SplitView.preferredWidth: 490
                    SplitView.minimumWidth: 360

                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.TextField {
                                id: searchField
                                Layout.fillWidth: true
                                placeholderText: "Search titles, comments, themes, Q&A, vibes…"
                                leftPadding: Kirigami.Units.gridUnit * 1.8
                            }
                            QQC2.ToolButton { icon.name: "edit-clear"; onClicked: searchField.clear() }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.ComboBox {
                                id: channelFilter
                                Layout.fillWidth: true
                                textRole: "text"
                                valueRole: "value"
                                model: [{ text: "All channels", value: "" }].concat(channels.map(function(channel) { return { text: channel.name, value: channel.name } }))
                            }
                            QQC2.CheckBox { id: staleOnly; text: "Stale only" }
                        }

                        QQC2.Label {
                            text: filteredSongs().length + " of " + songs.length + " songs"
                            opacity: 0.65
                        }

                        ListView {
                            id: songList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: filteredSongs()
                            spacing: Kirigami.Units.smallSpacing
                            ScrollBar.vertical: QQC2.ScrollBar {}

                            delegate: Kirigami.AbstractCard {
                                width: songList.width
                                highlighted: songList.currentIndex === index
                                onClicked: {
                                    songList.currentIndex = index
                                    chooseSong(modelData)
                                }

                                contentItem: RowLayout {
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        QQC2.Label { text: modelData.title || modelData.fileName; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                                        QQC2.Label { text: modelData.channel + (modelData.artist ? "  ·  " + modelData.artist : ""); opacity: 0.7; elide: Text.ElideRight; Layout.fillWidth: true }
                                        QQC2.Label { text: modelData.comment || "No public comment"; opacity: 0.6; elide: Text.ElideRight; Layout.fillWidth: true }
                                    }
                                    Kirigami.Icon { source: "dialog-warning"; visible: modelData.staleComment; color: Kirigami.Theme.neutralTextColor }
                                    Kirigami.Icon { source: "folder-locked"; visible: modelData.blockedChannel; color: Kirigami.Theme.negativeTextColor }
                                }
                            }

                            Kirigami.PlaceholderMessage {
                                anchors.centerIn: parent
                                visible: songList.count === 0
                                text: songs.length === 0 ? "Load the Midori AI Radio library" : "No songs match this filter"
                                helpfulAction: Kirigami.Action { text: "Refresh Library"; icon.name: "view-refresh"; onTriggered: refreshLibrary() }
                            }
                        }
                    }
                }

                Kirigami.ScrollablePage {
                    SplitView.fillWidth: true
                    title: selectedSong ? (selectedSong.title || selectedSong.fileName) : "Song metadata"

                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing

                        Kirigami.PlaceholderMessage {
                            visible: !selectedSong
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            text: "Choose a song to edit its Midori AI Radio metadata"
                        }

                        GridLayout {
                            visible: !!selectedSong
                            columns: 2
                            columnSpacing: Kirigami.Units.largeSpacing
                            rowSpacing: Kirigami.Units.smallSpacing
                            Layout.fillWidth: true

                            QQC2.Label { text: "Title" }
                            QQC2.TextField { id: titleField; Layout.fillWidth: true }
                            QQC2.Label { text: "Artist" }
                            QQC2.TextField { id: artistField; Layout.fillWidth: true }
                            QQC2.Label { text: "Album" }
                            QQC2.TextField { id: albumField; Layout.fillWidth: true }
                            QQC2.Label { text: "Genre" }
                            QQC2.TextField { id: genreField; Layout.fillWidth: true }
                        }

                        QQC2.Label { visible: !!selectedSong; text: "Public comment"; font.bold: true }
                        QQC2.TextArea { id: commentField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 92 }

                        Kirigami.Heading { visible: !!selectedSong; text: "Midori AI Radio fields"; level: 3 }
                        QQC2.Label { visible: !!selectedSong; text: "Why I made this song" }
                        QQC2.TextArea { id: whyMadeField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 72 }
                        QQC2.Label { visible: !!selectedSong; text: "Backstory" }
                        QQC2.TextArea { id: backstoryField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 72 }
                        QQC2.Label { visible: !!selectedSong; text: "Why this song is on Midori AI Radio" }
                        QQC2.TextArea { id: radioReasonField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 72 }
                        QQC2.Label { visible: !!selectedSong; text: "Music theme" }
                        QQC2.TextArea { id: musicThemeField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 72 }
                        QQC2.Label { visible: !!selectedSong; text: "Listener takeaway" }
                        QQC2.TextArea { id: takeawayField; visible: !!selectedSong; Layout.fillWidth: true; wrapMode: TextEdit.Wrap; implicitHeight: 72 }

                        Kirigami.InlineMessage {
                            visible: !!selectedSong && selectedSong.vibeSummary
                            text: "Cached vibe: " + (selectedSong ? selectedSong.vibeSummary : "")
                            type: Kirigami.MessageType.Information
                            Layout.fillWidth: true
                        }

                        RowLayout {
                            visible: !!selectedSong
                            Layout.fillWidth: true
                            QQC2.Button { text: "Play"; icon.name: "media-playback-start"; onClicked: runResult(backend.playSong(selectedSong.path)) }
                            QQC2.Button { text: "Open Folder"; icon.name: "document-open-folder"; onClicked: runResult(backend.openPath(selectedSong.path.substring(0, selectedSong.path.lastIndexOf("/")))) }
                            QQC2.Button {
                                text: "Move to Trash"
                                icon.name: "user-trash"
                                onClicked: trashDialog.open()
                            }
                            Item { Layout.fillWidth: true }
                            QQC2.Button {
                                text: "Save Metadata"
                                icon.name: "document-save"
                                highlighted: true
                                onClicked: {
                                    const payload = {
                                        path: selectedSong.path,
                                        title: titleField.text,
                                        artist: artistField.text,
                                        album: albumField.text,
                                        genre: genreField.text,
                                        comment: commentField.text,
                                        whyMade: whyMadeField.text,
                                        backstory: backstoryField.text,
                                        radioReason: radioReasonField.text,
                                        musicTheme: musicThemeField.text,
                                        listenerTakeaway: takeawayField.text
                                    }
                                    runResult(backend.saveSongMetadata(JSON.stringify(payload)), function(data) {
                                        refreshLibrary()
                                    })
                                }
                            }
                        }
                    }
                }
            }

            QQC2.Dialog {
                id: trashDialog
                anchors.centerIn: parent
                modal: true
                title: "Move this song to Trash?"
                standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
                onAccepted: {
                    if (!selectedSong)
                        return
                    runResult(backend.trashSong(selectedSong.path), function() { refreshLibrary() })
                }
                contentItem: QQC2.Label { text: selectedSong ? selectedSong.fileName : ""; wrapMode: Text.Wrap }
            }
        }

        Kirigami.ScrollablePage {
            title: "Import music into Midori AI Radio"

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.largeSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading { text: "Newest MP3 files in Downloads"; level: 2; Layout.fillWidth: true }
                    QQC2.Button { text: "Refresh Downloads"; icon.name: "view-refresh"; onClicked: refreshDownloads() }
                }

                Kirigami.InlineMessage {
                    Layout.fillWidth: true
                    text: "Files marked as already imported share a filename with a song somewhere in the current library. Import still uses a collision-safe destination name."
                    type: Kirigami.MessageType.Information
                    visible: true
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, 430)
                    model: downloads
                    clip: true
                    spacing: Kirigami.Units.smallSpacing

                    delegate: Kirigami.AbstractCard {
                        width: ListView.view.width
                        contentItem: RowLayout {
                            Kirigami.Icon { source: modelData.alreadyImported ? "dialog-warning" : "audio-mpeg" }
                            ColumnLayout {
                                Layout.fillWidth: true
                                QQC2.Label { text: modelData.fileName; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                                QQC2.Label { text: modelData.path; opacity: 0.6; Layout.fillWidth: true; elide: Text.ElideMiddle }
                            }
                            QQC2.Label { text: modelData.alreadyImported ? "Possibly imported" : "New"; color: modelData.alreadyImported ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.positiveTextColor }
                        }
                    }
                }

                Kirigami.Separator { Layout.fillWidth: true }

                RowLayout {
                    Layout.fillWidth: true
                    QQC2.Label { text: "Destination channel"; font.bold: true }
                    QQC2.ComboBox {
                        id: importChannel
                        Layout.fillWidth: true
                        model: channels.map(function(channel) { return channel.name })
                    }
                    QQC2.Button {
                        text: "Choose MP3 Files"
                        icon.name: "document-import"
                        enabled: importChannel.currentText.length > 0
                        highlighted: true
                        onClicked: importDialog.open()
                    }
                }
            }
        }

        Kirigami.ScrollablePage {
            title: "Midori AI Radio channels"

            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Heading { text: channels.length + " channels"; level: 2 }

                Repeater {
                    model: channels
                    delegate: Kirigami.Card {
                        Layout.fillWidth: true
                        contentItem: RowLayout {
                            Kirigami.Icon { source: modelData.blocked ? "folder-locked" : "folder-music"; implicitWidth: 42; implicitHeight: 42 }
                            ColumnLayout {
                                Layout.fillWidth: true
                                QQC2.Label { text: modelData.name; font.bold: true; font.pixelSize: Kirigami.Theme.defaultFont.pixelSize * 1.15 }
                                QQC2.Label { text: modelData.songCount + " songs · " + modelData.staleCount + " stale comments"; opacity: 0.7 }
                                QQC2.Label { text: modelData.path; opacity: 0.55; elide: Text.ElideMiddle; Layout.fillWidth: true }
                            }
                            QQC2.Button { text: "Open"; icon.name: "document-open-folder"; onClicked: runResult(backend.openPath(modelData.path)) }
                            QQC2.Button {
                                text: modelData.blocked ? "Unblock" : "Block"
                                icon.name: modelData.blocked ? "object-unlocked" : "object-locked"
                                onClicked: {
                                    const payload = { root: libraryRoot.text.trim(), channel: modelData.name, blocked: !modelData.blocked }
                                    runResult(backend.setChannelBlocked(JSON.stringify(payload)), function() { refreshLibrary() })
                                }
                            }
                        }
                    }
                }
            }
        }

        Item {
            SplitView {
                anchors.fill: parent
                orientation: Qt.Horizontal

                Kirigami.ScrollablePage {
                    SplitView.preferredWidth: 560
                    SplitView.minimumWidth: 430
                    title: "Prompt Lab"

                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.ComboBox {
                                id: promptSelector
                                Layout.fillWidth: true
                                textRole: "text"
                                valueRole: "value"
                                model: [
                                    { text: "Song comment", value: "comment" },
                                    { text: "Refine comment", value: "refine_comment" },
                                    { text: "Q&A cleanup", value: "qna_cleanup" },
                                    { text: "Q&A inference", value: "qna_guess" },
                                    { text: "Channel recommendation", value: "channel_recommendation" }
                                ]
                                onCurrentValueChanged: {
                                    selectedPromptKey = currentValue || "comment"
                                    promptEditor.text = (promptStore.prompts || {})[selectedPromptKey] || ""
                                }
                            }
                            QQC2.Label { id: promptVersion; text: "Prompt set v0"; opacity: 0.65 }
                        }

                        QQC2.Label { text: "Reusable prompt"; font.bold: true }
                        QQC2.TextArea {
                            id: promptEditor
                            Layout.fillWidth: true
                            Layout.preferredHeight: 230
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                        }

                        Kirigami.InlineMessage {
                            Layout.fillWidth: true
                            visible: true
                            type: Kirigami.MessageType.Information
                            text: "Prompt updates are stored in your XDG config and version history. They never edit or dirty the monorepo."
                        }

                        QQC2.Label { id: promptSongLabel; text: selectedSong ? selectedSong.title : "Choose a song in Library first"; font.bold: true }
                        QQC2.TextArea {
                            id: operatorNotes
                            Layout.fillWidth: true
                            implicitHeight: 80
                            placeholderText: "Optional direction for this generation, such as what detail matters most."
                            wrapMode: TextEdit.Wrap
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.Button {
                                text: "Generate Draft"
                                icon.name: "tools-wizard"
                                enabled: !!selectedSong && !busy
                                highlighted: true
                                onClicked: {
                                    busy = true
                                    const payload = {
                                        root: libraryRoot.text.trim(),
                                        promptKey: selectedPromptKey,
                                        songPath: selectedSong.path,
                                        notes: operatorNotes.text,
                                        model: modelField.text.trim(),
                                        variant: variantField.text.trim(),
                                        fallbackModel: fallbackModelField.text.trim(),
                                        fallbackVariant: fallbackVariantField.text.trim()
                                    }
                                    const raw = backend.runSongPrompt(JSON.stringify(payload))
                                    busy = false
                                    runResult(raw, function(data) {
                                        generatedOutput.text = data.output || ""
                                        promptPreview.text = data.promptPreview || ""
                                    })
                                }
                            }
                            QQC2.Button {
                                text: "Copy Draft to Comment"
                                enabled: !!selectedSong && generatedOutput.text.trim().length > 0
                                onClicked: commentField.text = generatedOutput.text.trim()
                            }
                        }

                        QQC2.Label { text: "Generated output"; font.bold: true }
                        QQC2.TextArea {
                            id: generatedOutput
                            Layout.fillWidth: true
                            Layout.preferredHeight: 150
                            wrapMode: TextEdit.Wrap
                            placeholderText: "The generated draft appears here."
                        }

                        QQC2.Label { text: "How was it?"; font.bold: true }
                        QQC2.ComboBox {
                            id: ratingField
                            Layout.fillWidth: true
                            model: ["Good", "Too long", "Too vague", "Too formal", "Wrong facts", "Other"]
                        }
                        QQC2.TextArea {
                            id: feedbackField
                            Layout.fillWidth: true
                            implicitHeight: 100
                            wrapMode: TextEdit.Wrap
                            placeholderText: "Write concrete feedback that should influence future generations."
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            QQC2.Button {
                                text: "Record Feedback"
                                icon.name: "document-save"
                                enabled: generatedOutput.text.trim().length > 0
                                onClicked: {
                                    const payload = {
                                        promptKey: selectedPromptKey,
                                        songPath: selectedSong ? selectedSong.path : "",
                                        output: generatedOutput.text,
                                        feedback: feedbackField.text,
                                        rating: ratingField.currentText
                                    }
                                    runResult(backend.recordFeedback(JSON.stringify(payload)), function() {
                                        feedbackField.clear()
                                        refreshPromptState()
                                    })
                                }
                            }
                            Item { Layout.fillWidth: true }
                            QQC2.Button {
                                text: "Reset Prompt"
                                icon.name: "edit-undo"
                                onClicked: runResult(backend.resetPrompt(selectedPromptKey), function() { refreshPromptState() })
                            }
                            QQC2.Button {
                                text: "Update Prompts"
                                icon.name: "view-refresh"
                                highlighted: true
                                enabled: feedbackForPrompt().length > 0 && !busy
                                onClicked: {
                                    busy = true
                                    const payload = {
                                        root: libraryRoot.text.trim(),
                                        promptKey: selectedPromptKey,
                                        currentPrompt: promptEditor.text,
                                        model: modelField.text.trim(),
                                        variant: variantField.text.trim(),
                                        fallbackModel: fallbackModelField.text.trim(),
                                        fallbackVariant: fallbackVariantField.text.trim()
                                    }
                                    const raw = backend.updatePrompts(JSON.stringify(payload))
                                    busy = false
                                    runResult(raw, function() { refreshPromptState() })
                                }
                            }
                        }

                        QQC2.Label { text: "Complete prompt preview"; font.bold: true }
                        QQC2.TextArea {
                            id: promptPreview
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            readOnly: true
                            wrapMode: TextEdit.Wrap
                            placeholderText: "If OpenCode is unavailable, this remains ready to copy into another model."
                        }
                    }
                }

                Kirigami.ScrollablePage {
                    SplitView.fillWidth: true
                    title: "Feedback history"

                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing

                        QQC2.Label {
                            text: feedbackForPrompt().length + " feedback entries for this prompt"
                            opacity: 0.7
                        }

                        Repeater {
                            model: feedbackForPrompt()
                            delegate: Kirigami.Card {
                                Layout.fillWidth: true
                                contentItem: ColumnLayout {
                                    RowLayout {
                                        Layout.fillWidth: true
                                        QQC2.Label { text: modelData.rating || "Unrated"; font.bold: true; color: modelData.rating === "Good" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor }
                                        Item { Layout.fillWidth: true }
                                        QQC2.Label { text: new Date((modelData.createdAtEpoch || 0) * 1000).toLocaleString(); opacity: 0.55 }
                                    }
                                    QQC2.Label { text: modelData.feedback || "No written feedback"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                    QQC2.Label { text: modelData.output || ""; wrapMode: Text.Wrap; Layout.fillWidth: true; opacity: 0.6; visible: text.length > 0 }
                                }
                            }
                        }

                        Kirigami.PlaceholderMessage {
                            visible: feedbackForPrompt().length === 0
                            text: "No feedback recorded for this prompt yet"
                            explanation: "Generate a draft, rate it, and record concrete feedback before using Update Prompts."
                        }
                    }
                }
            }
        }
    }
}
