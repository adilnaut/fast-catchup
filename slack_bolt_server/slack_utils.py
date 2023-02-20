from connection import db_ops, get_current_user
from bolt import app
import time



def etl_channels(app):
    # save all conversations
    response = app.client.conversations_list(types='public_channel,private_channel,im, mpim')
    status = response.get('ok')
    channels = response.get('channels')
    if status and channels:
        for channel in channels:
            id = channel.get('id')
            name = channel.get('name')
            is_channel = channel.get('is_channel')
            is_group = channel.get('is_group')
            is_im = channel.get('is_im')
            created = channel.get('created')
            creator = channel.get('creator')
            is_archived = channel.get('is_archived')
            is_general = channel.get('is_general')
            unlinked = channel.get('unlinked')
            name_normalized = channel.get('name_normalized')
            is_shared = channel.get('is_shared')
            is_ext_shared = channel.get('is_ext_shared')
            is_org_shared = channel.get('is_org_shared')
            is_pending_ext_shared = channel.get('is_pending_ext_shared')
            is_member = channel.get('is_member')
            is_private = channel.get('is_private')
            is_mipm = channel.get('is_mpim')
            topic = channel.get('topic')
            if topic:
                topic = topic.get('value')
            purpose = channel.get('purpose')
            if purpose:
                purpose = purpose.get('value')
            num_members = channel.get('num_members')
            slack_channel_kwargs = {'id':id
                            , 'name':name
                            , 'is_channel':is_channel
                            , 'is_group':is_group
                            , 'is_im':is_im
                            , 'created':created
                            , 'creator':creator
                            , 'is_archived':is_archived
                            , 'is_general':is_general
                            , 'unlinked':unlinked
                            , 'name_normalized':name_normalized
                            , 'is_shared':is_shared
                            , 'is_ext_shared':is_ext_shared
                            , 'is_org_shared':is_org_shared
                            , 'is_pending_ext_shared':is_pending_ext_shared
                            , 'is_member':is_member
                            , 'is_private':is_private
                            , 'is_mipm':is_mipm
                            , 'topic':topic
                            , 'purpose':purpose
                            , 'num_members':num_members}
            with db_ops(model_names=['SlackChannel']) as (db, SlackChannel):
                slack_channel = SlackChannel(**slack_channel_kwargs)
                db.session.add(slack_channel)

def etl_users(app):
    response = app.client.users_list()
    status = response.get('ok')
    members = response.get('members')
    # don't overwhelm API rate

    if status and members:
        for member in members:
            id = member.get('id')
            name = member.get('name')
            team_id = member.get('team_id')
            deleted = member.get('deleted')
            color = member.get('color')
            real_name = member.get('real_name')
            tz = member.get('tz')
            tz_label = member.get('tz_label')
            tz_offset = member.get('tz_offset')
            profile = member.get('profile')
            if profile:
                profile_avatar_hash = profile.get('avatar_hash')
                profile_status_text = profile.get('status_text')
                profile_status_emoji = profile.get('status_emoji')
                profile_real_name = profile.get('real_name')
                profile_display_name = profile.get('display_name')
                profile_real_name_normalized = profile.get('real_name_normalized')
                profile_display_name_normalized = profile.get('display_name_normalized')
                profile_email = profile.get('email')
                profile_image_24 = profile.get('image_24')
                profile_image_32 = profile.get('image_32')
                profile_image_48 = profile.get('image_48')
                profile_image_72 = profile.get('image_72')
                profile_image_192 = profile.get('image_192')
                profile_image_512 = profile.get('image_512')
                profile_team = profile.get('team')
            is_admin = member.get('is_admin')
            is_owner = member.get('is_owner')
            is_primary_owner = member.get('is_primary_owner')
            is_restricted = member.get('is_restricted')
            is_ultra_restricted = member.get('is_ultra_restricted')
            is_bot = member.get('is_bot')
            updated = member.get('updated')
            is_app_user = member.get('is_app_user')
            has_2fa = member.get('has_2fa')
            slack_users_kwargs = {'id':id
                , 'name':name
                , 'team_id':team_id
                , 'deleted':deleted
                , 'color':color
                , 'real_name':real_name
                , 'tz':tz
                , 'tz_label':tz_label
                , 'tz_offset':tz_offset
                , 'profile_avatar_hash':profile_avatar_hash
                , 'profile_status_text':profile_status_text
                , 'profile_status_emoji':profile_status_emoji
                , 'profile_real_name':profile_real_name
                , 'profile_display_name':profile_display_name
                , 'profile_real_name_normalized':profile_real_name_normalized
                , 'profile_display_name_normalized':profile_display_name_normalized
                , 'profile_email':profile_email
                , 'profile_image_24':profile_image_24
                , 'profile_image_32':profile_image_32
                , 'profile_image_48':profile_image_48
                , 'profile_image_72':profile_image_72
                , 'profile_image_192':profile_image_192
                , 'profile_image_512':profile_image_512
                , 'profile_team':profile_team
                , 'is_admin':is_admin
                , 'is_owner':is_owner
                , 'is_primary_owner':is_primary_owner
                , 'is_restricted':is_restricted
                , 'is_ultra_restricted':is_ultra_restricted
                , 'is_bot':is_bot
                , 'updated':updated
                , 'is_app_user':is_app_user
                , 'has_2fa':has_2fa
            }
            with db_ops(model_names=['SlackUser']) as (db, SlackUser):
                slack_user = SlackUser(**slack_users_kwargs)
                db.session.add(slack_user)


def etl_messages(app, days_ago=1, max_pages=1,  verbose=False):
    # don't overwhelm API rate
    slack_channels = None

    with db_ops(model_names=['SlackChannel']) as (db, SlackChannel):
        platform_id = get_platform_id()
        if platform_id:
            slack_channels = SlackChannel.query.filter_by(platform_id=platform_id).all()

    yesterday = datetime.utcnow() - timedelta(days=days_ago)
    unix_time = time.mktime(yesterday.timetuple())

    for channel in slack_channels:
        next_cursor = None
        for i in range(max_pages):
            # don't overwhelm API rate
            time.sleep(0.2)
            if verbose:
                print("channel %s, id %s, request number %s" % (channel.name,
                    channel.id, i))
            if next_cursor:
                response = app.client.conversations_history(channel=channel.id, oldest=unix_time,
                    limit=100, cursor=next_cursor)
            else:
                response = app.client.conversations_history(channel=channel.id,
                    oldest=unix_time, include_all_metadata='true', limit=100)
            status = response.get('ok')
            response_metadata = response.get('response_metadata')
            if response_metadata:
                next_cursor = response_metadata.get('next_cursor')
            has_more = response.get('has_more')

            messages = response.get('messages')
            if verbose:
                print("Has more %s, messages %s" % (has_more, len(messages)))
            if status and messages:
                for message in messages:
                    type = message.get('type')
                    user = message.get('user')
                    text = message.get('text')
                    channel_id = message.get('channel')
                    ts = message.get('ts')
                    with db_ops(model_names=['SlackMessage']) as (db, SlackMessage):
                        is_message = SlackMessage.query.filter_by(ts=ts).first()
                        if not is_message:
                            slack_message_kwargs = {'ts': ts
                                , 'type': type
                                , 'slack_user_id': user
                                , 'text': text
                                , 'slack_channel_id': channel_id
                                , 'is_unread': True
                                }
                            s_message = SlackMessage(**slack_message_kwargs)
                            db.session.add(s_message)
            if not has_more:
                break;

if __name__ == '__main__':
    etl_users(app)
    etl_channels(app)
