import praw

reddit = praw.Reddit(user_agent='rocketscanner/1.0')
print("Mode: read-only")

try:
    user = reddit.redditor('theultimator5')
    user._fetch()
    print("User:", user.name, "Link karma:", user.link_karma)
    
    print("\n=== SUBMISSIONS ===")
    count = 0
    for sub in user.submissions.new(limit=50):
        count += 1
        title = sub.title
        score = sub.score
        subreddit = str(sub.subreddit)
        permalink = sub.permalink
        print(str(count) + ". " + title)
        print("   Score:", score, "| r/" + subreddit)
        print("   URL: https://www.reddit.com" + permalink)
        if sub.selftext:
            print("   Text:", sub.selftext[:500].replace('\n', ' '))
        print()
        if count >= 30:
            break
    
    print("\n=== COMMENTS ===")
    count = 0
    for c in user.comments.new(limit=50):
        count += 1
        print(str(count) + ". [" + str(c.subreddit) + "] score:" + str(c.score))
        print("   Comment:", str(c.body)[:300].replace('\n', ' '))
        print()
        
except Exception as e:
    print("Error:", type(e).__name__, str(e))
    import traceback
    traceback.print_exc()
