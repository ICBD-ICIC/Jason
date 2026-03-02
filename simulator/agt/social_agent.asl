/* ==========================================================
   Available Environment Actions
   
    updateFeed
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)

    searchContent(+Topic)
        Topic: string/atom
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)

    searchAuthor(+Author)
        Author: string/atom
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)

    createPost(+Topics, +Variables, +Content)
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    repost(+Id)
        Id: number

    comment(+Id, +Topics, +Variables, +Content)
        Id: number
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    react(+Id, +Reaction)
        Id: number
        Reaction: string/atom, e.g. like or "love"

    ask(+Query)
        Queries the common knowledge base.
        Query: any knowledge literal, e.g. weather(london, W)
        Percepts added: grounded literals matching the query, e.g. weather(london, sunny)

    createLink(+Agent)
        Agent: string/atom
        Percepts added: follows(Agent) for self        
                        followedBy(Self) for target

    removeLink(+Agent)
        Agent: string/atom
        Percepts removed: follows(Agent) for self
                          followedBy(Self) for target

    readPublicProfile(+Agent)
        Agent: string/atom 
        Percepts added: public_profile(Agent, Attribute, Value)
    ========================================================== */
