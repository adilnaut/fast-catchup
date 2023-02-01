import os
import json

from connection import db_ops


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
    verbose = False
    if verbose:
        logger.info("Some general message received!")
        logger.info(body)

    export_sample = False
    if export_sample:
        with open('slack_bolt/output_body','w') as d:
            json.dump(body, d, indent=4)

    event = body.get('event')

    if not event:
        if verbose:
            logger.info("Message body doesn't contain event!")
        return

    user_id = event.get('user')
    text = event.get('text')
    ts = event.get('ts')
    type = event.get('type')
    channel_id = event.get('channel')
    channel_type = event.get('channel_type')
    team_id = event.get('team')

    if not ts:
        if verbose:
            logger.info("No primary key - timestamp ts for slack user!")
        return

    slack_message_kwargs = {
        'ts': ts,
        'text': text,
        'type': type,
        'is_unread': True, # todo check out if you should mark them false anytime
        'slack_user_id': user_id,
        'slack_channel_id': channel_id
    }
    with db_ops(model_names=['SlackMessage']) as (db, SlackMessage):
        slack_message = SlackMessage(**slack_message_kwargs)
        db.session.add(slack_message)
        if verbose:
            logger.info("Slack message with ts %s added successfully!" % ts)



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
