import praw
from praw.reddit import Reddit
from praw.models import Submission, MoreComments
from utils.helpers import load_config, load_database, sanitize_text
from tinydb import Query
import json
from playwright.sync_api import ViewportSize, sync_playwright, BrowserContext


def login() -> Reddit:
    """
    Logs into Reddit using credentials from the configuration file.

    Returns:
        Reddit: The Reddit instance after successful login.

    Raises:
        Exception: If login fails, the exception is returned.
    """
    my_config = load_config()
    try:
        reddit = praw.Reddit(
            client_id=my_config['RedditCredential']['client_id'],
            client_secret=my_config['RedditCredential']['client_secret'],
            user_agent="Accessing Reddit Threads",
            username=my_config["RedditCredential"]["username"],
            password=my_config["RedditCredential"]["passkey"],
            check_for_async=False
        )
        print("Bot logged in to Reddit successfully!")
        return reddit
    except Exception as e:
        print(f"Failed to login to Reddit: {e}")
        raise e


def get_thread(reddit: Reddit, subreddit: str) -> Submission:
    """
    Retrieves the top thread from a subreddit that is not already in the database.

    Args:
        reddit (Reddit): The Reddit instance.
        subreddit (str): The name of the subreddit.

    Returns:
        Submission: The top thread not already in the database.
    """
    # Access the subreddit
    subreddit_instance = reddit.subreddit(subreddit)

    # Get the top threads of the week
    threads = subreddit_instance.top('week')

    # Sort threads based on the number of upvotes in descending order
    sorted_threads = sorted(threads, key=lambda x: x.score, reverse=True)

    # Load the database
    db = load_database()
    chosen_thread = None

    # Find the top thread that is not already in the database
    for thread in sorted_threads:
        if not db.search(Query().id == str(thread.id)):
            print(f"Chosen thread: {thread.title} -- Score: {thread.score}")
            chosen_thread = thread
            break

    db.close()
    return chosen_thread


def get_comments(thread: Submission) -> list:
    """
    Retrieves and sanitizes top-level comments from a Reddit thread.

    Args:
        thread (Submission): The Reddit thread.

    Returns:
        list: A list of sanitized top-level comments.
    """
    # Load configuration settings
    my_config = load_config()
    topn = my_config['Reddit']['topn_comments']
    comments = []

    # Iterate through the top-level comments of the thread
    for top_level_comment in thread.comments:
        if len(comments) >= topn:
            break
        if isinstance(top_level_comment, MoreComments):
            continue
        if top_level_comment.body in ["[removed]", "[deleted]"]:
            continue
        if not top_level_comment.stickied:
            sanitized = sanitize_text(top_level_comment.body)
            if sanitized and (my_config["Reddit"]["min_comment_length"] <= len(top_level_comment.body)
                              and len(top_level_comment.body) <= my_config["Reddit"]["max_comment_length"]):
                comments.append(top_level_comment)

    print(f"{len(comments)} comments are chosen")
    return comments


def clear_cookie_by_name(context: BrowserContext, cookie_name: str):
    """
    Clears a specific cookie by its name in the browser context.

    Args:
        context (BrowserContext): The browser context.
        cookie_name (str): The name of the cookie to clear.
    """
    # Get all cookies in the browser context
    cookies = context.cookies()

    # Filter out the cookie that needs to be cleared
    filtered_cookies = [cookie for cookie in cookies if cookie["name"] != cookie_name]

    # Clear all cookies
    context.clear_cookies()

    # Add back the filtered cookies (excluding the one to be cleared)
    context.add_cookies(filtered_cookies)


def get_screenshots_of_reddit_posts(reddit_thread: Submission, reddit_comments: list):
    """
    Takes screenshots of a Reddit thread and its comments using Playwright.

    Args:
        reddit_thread (Submission): The Reddit thread.
        reddit_comments (list): A list of Reddit comments.
    """
    my_config = load_config()

    # Settings for screenshot dimensions
    W = my_config["settings"]["resolution_h"]
    H = my_config["settings"]["resolution_w"]

    # Launch Playwright browser
    with sync_playwright() as p:
        print("Launching browser...")

        browser = p.chromium.launch(headless=True)

        theme = my_config["settings"]["theme"]

        # Calculate device scale factor
        dsf = (W // 600) + 1

        # Create a new browser context with specified settings
        context = browser.new_context(
            locale="en-us",
            color_scheme=theme,
            viewport=ViewportSize(width=W, height=H),
            device_scale_factor=dsf,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )

        with open(f"./assets/cookie-{theme}-mode.json", encoding="utf-8") as cookie_file:
            cookies = json.load(cookie_file)
            cookie_file.close()
            context.add_cookies(cookies)

        # Open a new page and log in to Reddit
        print("Opening Reddit...")
        page = context.new_page()
        page.goto("https://www.reddit.com/login", timeout=0)
        page.set_viewport_size(ViewportSize(width=1920, height=1080))
        page.wait_for_load_state()

        # Fill in login credentials and submit
        print("Logging into Reddit...")
        page.locator('input[name="username"]').fill(my_config["RedditCredential"]["username"])
        page.locator('input[name="password"]').fill(my_config["RedditCredential"]["passkey"])
        page.get_by_role("button", name="Log In").click()
        page.wait_for_timeout(5000)

        # Handle Reddit redesign opt-out if necessary
        if page.locator("#redesign-beta-optin-btn").is_visible():
            clear_cookie_by_name(context, "redesign_optout")
            page.reload()

        # Navigate to the Reddit thread
        print("Navigating to Reddit thread...")
        page.goto(f"https://new.reddit.com{reddit_thread.permalink}", timeout=0)
        page.set_viewport_size(ViewportSize(width=W, height=H))
        page.wait_for_timeout(5000)

        # Wait for the dropdown menu to be visible and click it
        print("Switching to the light/dark mode...")
        dropdown_menu_selector = "#USER_DROPDOWN_ID > span.DFKWwVItcycZV1bKUOyay > i"
        page.wait_for_selector(dropdown_menu_selector)
        page.locator(dropdown_menu_selector).click()
        page.wait_for_timeout(2000)

        # Locate and click the dark mode button
        dark_mode_button_selector = "button[aria-checked='false'][role='switch']"
        dark_mode_button = page.locator(dark_mode_button_selector)
        page.wait_for_timeout(2000)

        # Ensure the dark mode button is visible
        if dark_mode_button.is_visible():
            is_dark_mode_enabled = dark_mode_button.get_attribute("aria-checked") == "true"
            if theme == "dark" and not is_dark_mode_enabled:
                dark_mode_button.click()
            elif theme == "light" and is_dark_mode_enabled:
                dark_mode_button.click()
        page.wait_for_timeout(2000)

        # Proceed with nsfw
        nsfw_proceed_button = (
            "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r"
            ".D3IL3FD0RFy_mkKLPwL4 > div > div > button"
        )
        if page.locator(nsfw_proceed_button).is_visible():
            page.locator(nsfw_proceed_button).click()
            page.wait_for_load_state()

        # Take screenshot of the post content
        op_path = f"./assets/temp/{reddit_thread.id}/png/title.png"
        if my_config["settings"]["zoom"] != 1:
            zoom = my_config["settings"]["zoom"]
            page.evaluate(f"document.body.style.zoom={zoom}")
            location = page.locator('[data-test-id="post-content"]').bounding_box()
            for key in location:
                location[key] = float("{:.2f}".format(location[key] * zoom))
            page.screenshot(clip=location, path=op_path)
            location = page.locator('[data-adclicklocation="title"]').bounding_box()
            for key in location:
                location[key] = float("{:.2f}".format(location[key] * zoom))
        else:
            page.locator('[data-test-id="post-content"]').screenshot(path=op_path)
        print("Saved: ", op_path)
        # print("Screenshot for OP completed")

        # Take screenshots of the comments
        for idx, comment in enumerate(reddit_comments):
            comments_path = f"./assets/temp/{reddit_thread.id}/png/{idx}.png"

            if page.locator('[data-testid="content-gate"]').is_visible():
                page.locator('[data-testid="content-gate"] button').click()

            page.goto(f'https://new.reddit.com{comment.permalink}', timeout=0)
            if my_config["settings"]["zoom"] != 1:
                zoom = my_config["settings"]["zoom"]
                page.evaluate(f"document.body.style.zoom={zoom}")
                location = page.locator(f"#t1_{comment.id}").bounding_box()
                for key in location:
                    location[key] = float("{:.2f}".format(location[key] * zoom))
                page.screenshot(clip=location, path=comments_path)
            else:
                page.locator(f"#t1_{comment.id}").screenshot(path=comments_path)
            print("Saved: ", comments_path)
            # print(f"Screenshot for {idx + 1} comment out of {len(reddit_comments)}")

        browser.close()

    print("Screenshots downloaded successfully.")

