import rply

lg = rply.lexergenerator.LexerGenerator()

lg.add("ROCKET", r"=>")

lg.add("LET", r"let")
lg.add("VAL", r"val")
lg.add("EQ", r"=")
lg.add("IN", r"in")
lg.add("END", r"end")

lg.add("IF", r"if")
lg.add("THEN", r"then")
lg.add("ELSE", r"else")

lg.add("FN", r"fn")  # for lambda expressions
lg.add("FUN", r"fun")  # for function definitions

lg.add("LPAREN", r"\(")
lg.add("RPAREN", r"\)")

lg.add("INT_LIT", r"\d+")
lg.add("BOOL_LIT", r"true|false")
lg.add("IDENT", r"[a-zA-A_][a-zA-Z0-9'_]*")

lg.ignore(r"\s+")

lexer = lg.build()
all_tokens = set(rule.name for rule in lexer.rules)