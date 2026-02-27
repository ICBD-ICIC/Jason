package env;

import jason.asSyntax.Literal;
import java.util.List;

public interface KnowledgeManager {
    /**
     * Returns all facts from the KB that unify with the given query literal.
     */
    List<Literal> query(Literal queryLiteral);
}