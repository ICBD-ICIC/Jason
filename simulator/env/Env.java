package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

import lib.JasonToJavaTranslator;
import lib.JavaToJasonTranslator;
import initializer.MessageLoader;
import initializer.NetworkLoader;
import initializer.PublicProfileLoader;

import java.lang.reflect.Constructor;


public class Env extends Environment {

    private static final Logger logger = Logger.getLogger(Env.class.getName());

    private final NetworkManager networkManager = new NetworkManager(this);
    private ContentManager contentManager;
    private KnowledgeManager knowledgeManager;
    private final Map<String, Map<String, Object>> publicProfiles = new ConcurrentHashMap<>();
    private final Map<String, List<Literal>> lastFeedPercepts = new ConcurrentHashMap<>();

    private static final String DEFAULT_CONTENT_MANAGER   = "DefaultContentManager";
    private static final String DEFAULT_KNOWLEDGE_MANAGER  = "DefaultKnowledgeManager";


    @Override
    public void init(String[] args) {
        Map<String, String> options = parseArgs(args);

        String contentManagerClass   = options.getOrDefault("contentManager", DEFAULT_CONTENT_MANAGER);
        String knowledgeManagerClass = options.getOrDefault("knowledgeManager", DEFAULT_KNOWLEDGE_MANAGER);

        this.contentManager   = instantiateContentManager(contentManagerClass);
        this.knowledgeManager = instantiateKnowledgeManager(knowledgeManagerClass);

        try {
            MessageLoader.load(contentManager, "initializer/messages.csv", logger);
            PublicProfileLoader.load(publicProfiles, "initializer/public_profiles.csv", logger);
            NetworkLoader.load(networkManager, "initializer/network.csv", logger);
        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize: " + e.getMessage(), e);
        }
    }

    private Map<String, String> parseArgs(String[] args) {
        Map<String, String> options = new HashMap<>();
        for (String arg : args) {
            int idx = arg.indexOf('=');
            if (idx > 0) {
                options.put(arg.substring(0, idx).trim(), arg.substring(idx + 1).trim());
            } else {
                logger.warning("[Env] Ignoring malformed environment argument: " + arg);
            }
        }
        return options;
    }

    private ContentManager instantiateContentManager(String className) {
        try {
            Class<?> clazz = resolveClass(className);
            Constructor<?> ctor = clazz.getConstructor(NetworkManager.class, Logger.class);
            return (ContentManager) ctor.newInstance(networkManager, logger);
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(
                "Failed to instantiate ContentManager '" + className + "'. " +
                "Expected a public constructor(NetworkManager, Logger): " + e.getMessage(), e);
        }
    }

    private KnowledgeManager instantiateKnowledgeManager(String className) {
        try {
            Class<?> clazz = resolveClass(className);
            Constructor<?> ctor = clazz.getConstructor();
            return (KnowledgeManager) ctor.newInstance();
        } catch (ReflectiveOperationException e) {
            throw new RuntimeException(
                "Failed to instantiate KnowledgeManager '" + className + "'. " +
                "Expected a public no-arg constructor: " + e.getMessage(), e);
        }
    }

    private Class<?> resolveClass(String className) throws ClassNotFoundException {
        return className.contains(".") ? Class.forName(className) : Class.forName("env." + className);
    }

    @Override
    public boolean executeAction(String agent, Structure action) {
        boolean result = switch (action.getFunctor()) {
            case "updateFeed"      -> updateFeed(agent, action);
            case "searchContent"   -> searchContent(agent, action);
            case "searchAuthor"    -> searchAuthor(agent, action);
            case "createPost"      -> createPost(agent, action);
            case "repost"          -> repost(agent, action);
            case "comment"         -> comment(agent, action);
            case "react"           -> react(agent, action);
            case "ask"             -> ask(agent, action);
            case "createLink"      -> createLink(agent, action);
            case "removeLink"      -> removeLink(agent, action);
            case "readPublicProfile" -> readPublicProfile(agent, action);
            default -> { logger.warning("[Env] Unknown action: " + action); yield true; }
        };
        return result;
    }

    private boolean updateFeed(String agent, Structure action) {
        boolean includePublicVars = action.getArity() >= 1
            && JasonToJavaTranslator.translateBoolean(action.getTerm(0));
        List<MessageWithVars> feed = contentManager.feedFilter(agent, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private boolean searchContent(String agent, Structure action) {
        String concept = JasonToJavaTranslator.translateString(action.getTerm(0));
        boolean includePublicVars = action.getArity() >= 2
            && JasonToJavaTranslator.translateBoolean(action.getTerm(1));
        List<MessageWithVars> feed = contentManager.topicFilter(agent, concept, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private boolean searchAuthor(String agent, Structure action) {
        String author = JasonToJavaTranslator.translateString(action.getTerm(0));
        boolean includePublicVars = action.getArity() >= 2
            && JasonToJavaTranslator.translateBoolean(action.getTerm(1));
        List<MessageWithVars> feed = contentManager.authorFilter(agent, author, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private void updatePercepts(String agent, List<MessageWithVars> messages, boolean includePublicVars) {
        // Remove only the feed-related literals added on the previous call.
        List<Literal> previous = lastFeedPercepts.get(agent);
        if (previous != null) {
            previous.forEach(lit -> removePercept(agent, lit));
        }

        List<Literal> current = new ArrayList<>();

        messages.forEach(mwv -> {
            Message m = mwv.message();

            Literal messageLit = createLiteral("message",
                createNumber(m.id),
                createString(m.author),
                createString(m.content),
                createNumber(m.original),
                createNumber(m.timestamp)
            );
            addPercept(agent, messageLit);
            current.add(messageLit);

            m.reactions.forEach(r -> {
                Literal reactionLit = createLiteral("reaction",
                    createNumber(m.id),
                    createString(r.author()),
                    createString(r.reaction())
                );
                addPercept(agent, reactionLit);
                current.add(reactionLit);
            });

            if (includePublicVars) {
                mwv.publicVars().forEach((key, value) -> {
                    Literal varLit = createLiteral("message_var",
                        createNumber(m.id),
                        createAtom(key),
                        JavaToJasonTranslator.objectToTerm(value)
                    );
                    addPercept(agent, varLit);
                    current.add(varLit);
                });
            }
        });

        List<Term> ids = messages.stream()
            .map(mwv -> (Term) createNumber(mwv.message().id))
            .toList();
        Literal feedOrderLit = createLiteral("feed_order", createList(ids));
        addPercept(agent, feedOrderLit);
        current.add(feedOrderLit);

        lastFeedPercepts.put(agent, current);
    }

    private boolean createPost(String agent, Structure action) {
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(0));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(1));
        String messageContent = JasonToJavaTranslator.translateString(action.getTerm(2));
        contentManager.addMessage(agent, messageContent, topics, variables);
        return true;
    }

    private boolean repost(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        contentManager.repost(agent, originalId);
        return true;
    }

    private boolean comment(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(1));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(2));
        String messageContent = JasonToJavaTranslator.translateString(action.getTerm(3));
        contentManager.addMessage(agent, messageContent, topics, variables, originalId);
        return true;
    }

    private boolean react(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        String reaction = JasonToJavaTranslator.translateString(action.getTerm(1));
        contentManager.addReaction(originalId, agent, reaction);
        return true;
    }

    private boolean createLink(String agent, Structure action) {
        String to = JasonToJavaTranslator.translateString(action.getTerm(0));
        networkManager.addEdge(agent, to);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followed_by", createString(agent)));
        return true;
    }

    private boolean removeLink(String agent, Structure action) {
        String to = JasonToJavaTranslator.translateString(action.getTerm(0));
        networkManager.removeEdge(agent, to);
        removePercept(agent, createLiteral("follows", createString(to)));
        removePercept(to, createLiteral("followed_by", createString(agent)));
        return true;
    }

    private boolean ask(String agent, Structure action) {
        try {
            Literal queryLiteral = (Literal) action.getTerm(0);
            List<Literal> results = knowledgeManager.query(queryLiteral);
            results.forEach(fact -> addPercept(agent, fact));
        } catch (Exception e) {
            logger.warning("[Env] Knowledge query failed for agent " + agent + ": " + e.getMessage());
        }
        return true;
    }

    private boolean readPublicProfile(String agent, Structure action) {
        String requestedAgent = JasonToJavaTranslator.translateString(action.getTerm(0));
        Map<String, Object> profile = publicProfiles.get(requestedAgent);
        if (profile != null) {
            profile.forEach((attribute, value) ->
                addPercept(agent, createLiteral("public_profile",
                    createAtom(requestedAgent),
                    createString(attribute),
                    JavaToJasonTranslator.objectToTerm(value)
                ))
            );
        }
        return true;
    }

    @Override
    public void stop() {
        super.stop();
        System.exit(0);
    }
}