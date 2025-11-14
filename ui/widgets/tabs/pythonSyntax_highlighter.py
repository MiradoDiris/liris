from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt5.QtCore import QRegularExpression


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    """✅ Coloration syntaxique Python pour QTextEdit."""
    
    def __init__(self, document):
        super().__init__(document)
        
        # ===== FORMATS DE COULEURS =====
        
        # Mots-clés
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569CD6"))  # Bleu
        self.keyword_format.setFontWeight(QFont.Bold)
        
        # Chaînes de caractères
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#CE9178"))  # Orange
        
        # Commentaires
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))  # Vert
        self.comment_format.setFontItalic(True)
        
        # Nombres
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#B5CEA8"))  # Vert clair
        
        # Fonctions/Méthodes
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#DCDCAA"))  # Jaune
        
        # Décorateurs
        self.decorator_format = QTextCharFormat()
        self.decorator_format.setForeground(QColor("#4EC9B0"))  # Cyan
        
        # Classes
        self.class_format = QTextCharFormat()
        self.class_format.setForeground(QColor("#4EC9B0"))  # Cyan
        self.class_format.setFontWeight(QFont.Bold)
        
        # ===== RÈGLES DE COLORATION =====
        
        self.highlighting_rules = []
        
        # Mots-clés Python
        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
            'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
            'while', 'with', 'yield', 'self', 'cls'
        ]
        
        for keyword in keywords:
            pattern = QRegularExpression(f'\\b{keyword}\\b')
            self.highlighting_rules.append((pattern, self.keyword_format))
        
        # Classes (class Xxx)
        self.highlighting_rules.append((
            QRegularExpression(r'\bclass\s+(\w+)'),
            self.class_format
        ))
        
        # Fonctions (def xxx)
        self.highlighting_rules.append((
            QRegularExpression(r'\bdef\s+(\w+)'),
            self.function_format
        ))
        
        # Décorateurs (@xxx)
        self.highlighting_rules.append((
            QRegularExpression(r'@\w+'),
            self.decorator_format
        ))
        
        # Nombres
        self.highlighting_rules.append((
            QRegularExpression(r'\b\d+\.?\d*\b'),
            self.number_format
        ))
        
        # Chaînes triple quotes ("""...""")
        self.highlighting_rules.append((
            QRegularExpression(r'"""[^"]*"""'),
            self.string_format
        ))
        
        # Chaînes triple quotes ('''...''')
        self.highlighting_rules.append((
            QRegularExpression(r"'''[^']*'''"),
            self.string_format
        ))
        
        # Chaînes (simple quotes)
        self.highlighting_rules.append((
            QRegularExpression(r"'[^']*'"),
            self.string_format
        ))
        
        # Chaînes (double quotes)
        self.highlighting_rules.append((
            QRegularExpression(r'"[^"]*"'),
            self.string_format
        ))
        
        # Commentaires
        self.highlighting_rules.append((
            QRegularExpression(r'#[^\n]*'),
            self.comment_format
        ))
    
    def highlightBlock(self, text):
        """Applique la coloration syntaxique à un bloc de texte."""
        for pattern, format_style in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            iterator = expression.globalMatch(text)
            
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(
                    match.capturedStart(), 
                    match.capturedLength(), 
                    format_style
                )