Liris dev:
UX/UI:
  - Configuration:
     ui/widgets/tabs/project_config_widget.py
     ui/widgets/tabs/relation_import_widget.py
  - Onglet Coding
     -ui/widgets/coding_panel.py
Worker:
  -Core/orchestration
Connexion dgraph et logique:
  -utils/dgraph_connector.py
  -utils/dgraph_project_manager.py

Voici les dialogue qui sont des enfants de coding_panel

from utils.dgraph_connector import LirisDgraphConnector
from ui.widgets.tabs.taxonomy_dialog import TaxonomyDialog
from ui.widgets.tabs.graph_widget import GraphWidget
from utils.api_config import APIConfigManager
from utils.ai_platform_manager import AIPlatformManager
from utils.conversation_history import ConversationHistory
from ui.widgets.tabs.code_popup_dialog import CodePopupDialog
from ui.widgets.tabs.snippet_card import SnippetCard
from utils.vscode_integration import VSCodeIntegration
from ui.widgets.tabs.session_history_manager import SessionHistoryDialog, load_session_into_history