import sys
import re
from urllib.parse import urlencode, parse_qsl
import xbmcgui, xbmc, xbmcplugin
import requests
import json

# Get the plugin url in plugin:// notation.
_URL = sys.argv[0]
# Get the plugin handle as an integer number.
_HANDLE = int(sys.argv[1])

base_url = u"https://pipes2.kan.org.il/api"
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Mobile Safari/537.36'})


# https://pipes2.kan.org.il/api/main?mainCatId=3&catType=1&from=1&to=200
# https://pipes2.kan.org.il/api/middle?catType=1&catId=68&mainCatId=3&index=1
# https://pipes2.kan.org.il/api/item?catType=1&catId=68
# https://pipes2.kan.org.il/api/item?catType=1&catId=1627&subCatId=389

def log(msg):
    xbmc.log(u"### [Kan11] - %s" % (msg,))


def get_url(**kwargs):
    """
    Create a URL for calling the plugin recursively from the given set of keyword arguments.
    :param kwargs: "argument=value" pairs
    :return: plugin call URL
    :rtype: str
    """
    return '{}?{}'.format(_URL, urlencode(kwargs))


def get_categories():
    """
    Get the list of video categories.
    Here you can insert some parsing code that retrieves
    the list of video categories (e.g. 'Movies', 'TV-shows', 'Documentaries' etc.)
    from some site or API.
    .. note:: Consider using `generator functions <https://wiki.python.org/moin/Generators>`_
        instead of returning lists.
    :return: The list of video categories
    :rtype: types.GeneratorType
    """
    url = base_url + "/main?mainCatId=3&catType=1&from=1&to=400"
    log(u"Getting url: %s" % (url,))
    response = session.get(url)
    categories = response.json()
    category_list = []

    for category in categories['entry']:
        category_list.append({
            'id': category['id'],
            'title': category['title'],
            'summary': category['summary'],
            'images': get_images(category['media_group'])
        })

    return category_list


def get_images(media_group):
    images = next((media for media in media_group if media['type'] == 'image'), None)
    if images:
        base = next(
            (image for image in images['media_item'] if image['type'] == 'image' and image['key'] == 'image_base'),
            None)
        poster = next(
            (image for image in images['media_item'] if
             image['type'] == 'image' and image['key'] == 'image_base_2x3'),
            base)
        thumb = next(
            (image for image in images['media_item'] if
             image['type'] == 'image' and image['key'] == 'image_base_1x1'),
            base)
        landscape = next((image for image in images['media_item'] if
                          image['type'] == 'image' and image['key'] == 'image_base_16x9'), base)

        landscape = re.sub(r'(imgid=\d+)_A(\..+)$', r'\1_B\2', landscape['src'])

        return {
            'poster': poster['src'],
            'thumb': thumb['src'],
            'icon': thumb['src'],
            'landscape': landscape,
            'fanart': landscape
        }

    return None


def get_videos(category):
    """
    Get the list of videofiles/streams.
    Here you can insert some parsing code that retrieves
    the list of video streams in the given category from some site or API.
    .. note:: Consider using `generators functions <https://wiki.python.org/moin/Generators>`_
        instead of returning lists.
    :param category: Category name
    :type category: str
    :return: the list of videos in the category
    :rtype: list
    """
    url = base_url + ("/item?catType=1&catId=%s" % category['id'])
    log(u"Getting url: %s" % (url,))
    response = session.get(url)
    videos = response.json()
    video_list = []

    for video in videos['entry']:
        if video['type']['value'] != 'video':
            continue
        tv_show = video['title'].split('|')
        rest = map(lambda x: x.strip(), tv_show[-1].split('-'))
        title = sorted(rest, key=lambda p: 1 if re.match(r"פרק \d+", p) else -1)[0]
        season_match = re.search(r'עונה (\d+)', video['title'])
        season = int(season_match.group(1)) if season_match else 1
        episode_match = re.search(r'פרק (\d+)', video['title'])
        episode = int(episode_match.group(1)) if episode_match else 1

        aired = video['published'].split('T')[0]
        year = int(aired.split('-')[0])
        video_list.append({
            'title': title,
            'season': season,
            'episode': episode,
            'plotoutline': video['summary'],
            'plot': video['extensions']['on_demand']['description'],
            'aired': aired,
            'year': year,
            'tvshowtitle': video['extensions']['on_demand']['show_name'],
            'duration': video['extensions']['duration'],
            'images': get_images(video['media_group']),
            'url': video['content']['src']
        })

    return video_list


def list_categories():
    """
    Create the list of video categories in the Kodi interface.
    """
    # Set plugin category. It is displayed in some skins as the name
    # of the current section.
    xbmcplugin.setPluginCategory(_HANDLE, 'Kan11 VOD')
    # Set plugin content. It allows Kodi to select appropriate views
    # for this type of content.
    xbmcplugin.setContent(_HANDLE, 'videos')
    # Get video categories
    categories = get_categories()
    # Iterate through categories
    for category in categories:
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=category['title'])
        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        # Here we use the same image for all items for simplicity's sake.
        # In a real-life plugin you need to set each image accordingly.
        if category['images']:
            list_item.setArt(category['images'])
        # Set additional info for the list item.
        # Here we use a category name for both properties for for simplicity's sake.
        # setInfo allows to set various information for an item.
        # For available properties see the following link:
        # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
        # 'mediatype' is needed for a skin to display info for this ListItem correctly.
        list_item.setInfo('video', {'title': category['title'],
                                    'plotoutline': category['summary'],
                                    'mediatype': 'video'})
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=listing&category=Animals
        url = get_url(action='listing', id=category["id"], title=category["title"])
        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = True
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_HANDLE)


def list_videos(category):
    # Set plugin category. It is displayed in some skins as the name
    # of the current section.
    xbmcplugin.setPluginCategory(_HANDLE, category['title'])
    # Set plugin content. It allows Kodi to select appropriate views
    # for this type of content.
    xbmcplugin.setContent(_HANDLE, 'videos')
    # Get the list of videos in the category.
    videos = get_videos(category)
    # Iterate through videos.
    for video in videos:
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=video['title'])
        # Set additional info for the list item.
        # 'mediatype' is needed for skin to display info for this ListItem correctly.
        list_item.setInfo('video', {'title': video['title'],
                                    'season': video['season'],
                                    'episode': video['episode'],
                                    'plotoutline': video['plotoutline'],
                                    'plot': video['plot'],
                                    'aired': video['aired'],
                                    'year': video['year'],
                                    'tvshowtitle': video['tvshowtitle'],
                                    'duration': video['duration'],
                                    'mediatype': 'video'})
        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        # Here we use the same image for all items for simplicity's sake.
        # In a real-life plugin you need to set each image accordingly.
        if video['images']:
            list_item.setArt(video['images'])
        # Set 'IsPlayable' property to 'true'.
        # This is mandatory for playable items!
        list_item.setProperty('IsPlayable', 'true')
        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=play&video=http://www.vidsplay.com/wp-content/uploads/2017/04/crab.mp4
        url = get_url(action='play', url=video['url'])
        # Add the list item to a virtual Kodi folder.
        # is_folder = False means that this item won't open any sub-list.
        is_folder = False
        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(_HANDLE, url, list_item, is_folder)
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    # xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_HANDLE)


def play_video(path):
    """
    Play a video by the provided path.
    :param path: Fully-qualified video URL
    :type path: str
    """
    log("original video %s" % path)
    url_parts = path.split('/')
    if 'entryId' in url_parts:
        entry_id = url_parts[url_parts.index('entryId') + 1]
        url = 'https://cdnapisec.kaltura.com/p/2717431/sp/271743100/embedIframeJs/uiconf_id/45733501/partner_id/2717431?iframeembed=true&playerId=playerid_45733501&entry_id=%s' % entry_id
        response_raw = requests.get(url)
        needle = "window.kalturaIframePackageData = "
        try:
            lines = list(filter(lambda line: needle in line, response_raw.text.split('\n')))
            if len(lines):
                first_line = lines[0]
                json_raw = json.loads(first_line[first_line.index(needle) + len(needle):-1])
                flavors = json_raw['entryResult']['contextData']['flavorAssets']
                flavors = sorted(flavors, key=lambda item: item['height'])
                asset = flavors[-1]
                if asset['height'] > 720:
                    urls_raw = requests.get(path).text
                    last_url = list(filter(lambda line: 'http' in line, urls_raw.split('\n')))[-1]
                    last_url_parts = last_url.split('/')
                    if 'flavorId' in last_url_parts:
                        path = last_url.replace(last_url_parts[last_url_parts.index('flavorId') + 1], asset['id'])
        except:
            log('video error, fallback to 720')
    # Create a playable item with a path to play.
    log("final video %s" % path)
    play_item = xbmcgui.ListItem(path=path)
    # Pass the item to the Kodi player.
    xbmcplugin.setResolvedUrl(_HANDLE, True, listitem=play_item)


def router(paramstring):
    """
    Router function that calls other functions
    depending on the provided paramstring
    :param paramstring: URL encoded plugin paramstring
    :type paramstring: str
    """
    # Parse a URL-encoded paramstring to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(paramstring))
    # Check the parameters passed to the plugin
    if params:
        log("params: %s" % params)
        if params['action'] == 'listing':
            # Display the list of videos in a provided category.
            list_videos({'id': params['id'], 'title': params['title']})
        elif params['action'] == 'play':
            # Play a video from a provided URL.
            play_video(params['url'])
        else:
            # If the provided paramstring does not contain a supported action
            # we raise an exception. This helps to catch coding errors,
            # e.g. typos in action names.
            raise ValueError('Invalid paramstring: {}!'.format(paramstring))
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories
        list_categories()


if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    router(sys.argv[2][1:])
