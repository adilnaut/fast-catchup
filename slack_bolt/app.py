import os
import json
# Use the package we installed
from slack_bolt import App
# from slack_bolt.adapter.socket_mode import SocketModeHandler
# Initializes your app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

import logging
logging.basicConfig(level=logging.DEBUG)
# Add functionality here
# @app.event("app_home_opened") etc
@app.event("app_home_opened")
def update_home_tab(client, event, logger):
  try:
    # views.publish is the method that your app uses to push a view to the Home tab
    client.views_publish(
      # the user that opened your app's app home
      user_id=event["user"],
      # the view object that appears in the app home
      view={
        "type": "home",
        "callback_id": "home_view",

        # body of the view
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Welcome to your _App's Home_* :tada:"
            }
          },
          {
            "type": "divider"
          },
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "This button won't do much for now but you can set up a listener for it using the `actions()` method and passing its unique `action_id`. See an example in the `examples` folder within your Bolt app."
            }
          },
          {
            "type": "actions",
            "elements": [
              {
                "type": "button",
                "text": {
                  "type": "plain_text",
                  "text": "Click me!"
                }
              }
            ]
          }
        ]
      }
    )

  except Exception as e:
    logger.error(f"Error publishing home tab: {e}")

# Listens to incoming messages that contain "hello"
# To learn available listener method arguments,
# visit https://slack.dev/bolt-python/api-docs/slack_bolt/kwargs_injection/args.html
@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Click Me"},
                    "action_id": "button_click",
                },
            }
        ],
        text=f"Hey there <@{message['user']}>!",
    )

@app.event("message")
def handle_message_events(client, body, logger, say):
    logger.info(body)
    with open('slack_bolt/output_body','w') as d:
        json.dump(body, d, indent=4)
    user_id = body['event']['user']
    text = body['event']['text']
    user_info = client.users_profile_get(user=user_id)
    # if 'ok' in user_info:
    #     user_name = user_info['profile']['display_name']
    #     with open('../unread_slack.txt', 'a') as f:
    #         f.write('%s wrote %s \n' % (user_name, text))
    logger.info("Some general message received!")
    logger.info("This was a text from %s saying %s" % (f"<@{user_id}>", text))
    # say("This was a text from %s saying %s" % (f"<@{user_id}>", text))
    # handle message text here

# action id changes arbitrary - might need a different identification
# @app.action("3i7Cw")
# def handle_some_action(ack, body, logger):
#     ack()
#     # logger.info(body)
#     logger.info("Home view button was pressed")
#     say(f"<@{body['user']['id']}> clicked the button")

@app.event("app_mention")
def handle_app_mention_events(body, logger, say):
    # logger.info(body)
    logger.info("This app was mentioned!")
    # this doesn't work because it would be a different path to get user id
    # say(f"Hey <@{body['user']['id']}>, I don't know what to say yet!")
    say("I don't know what to say yet!")


@app.action("button_click")
def action_button_click(body, ack, say):
    # Acknowledge the action
    ack()
    say(f"<@{body['user']['id']}> clicked the button")
    # logger.info("This is logger 3")

# Start your app
if __name__ == "__main__":
    # SocketModeHandler(app, os.environ.get("SLACK_SCOPE_TOKEN")).start()
    app.start(port=int(os.environ.get("PORT", 3000)))
