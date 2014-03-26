from coldsweat import hook

@hook('entry_fetched')
def something(entry):
    print 'Hello'
