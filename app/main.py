# -*- coding: utf-8 -*-
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.image import AsyncImage as Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.storage.jsonstore import JsonStore
from kivy.clock import Clock
from kivy.uix.progressbar import ProgressBar

from os.path import join
import os
from functools import partial
from BeautifulSoup import BeautifulSoup as BS

import requests
import json
import re

data_dir = ""


class ThumbButton(ButtonBehavior, Image):

    gallery_id = StringProperty("")
    gallery_token = StringProperty("")
    gallery_name = StringProperty("")
    pagecount = NumericProperty(0)


class FrontScreen(Screen):

    global data_dir

    pb = ProgressBar(max=4500)
    gallery_thumbs = ListProperty([])
    gidlist = ListProperty([])
    searchword = StringProperty("")
    searchpage = NumericProperty(0)

    def on_enter(self):

        search_store = JsonStore(join(data_dir, 'search_store.json'))
        if search_store.exists("searchstring"):
            self.searchword = search_store["searchstring"]["searchphrase"]
        else:
            self.searchword = ""

        self.ids.main_layout.clear_widgets()
        self.searchpage = 0

        self.pb.value = 0
        self.gallery_thumbs = []

        for i in range(10):
            Clock.schedule_once(self.increasepb, i)

        self.ids.main_layout.add_widget(self.pb)

        Clock.schedule_once(partial(self.populate_front, "0"), 5)

    def increasepb(self, state):
        self.pb.value += 450
        if self.pb.value == 4500:
            self.ids.main_layout.remove_widget(self.pb)

    def enter_gallery(self, state):
        gallery_store = JsonStore(join(data_dir, 'gallerystore.json'))
        galleryinfo = [state.gallery_id, state.gallery_token, state.pagecount,
                       state.gallery_name]
        gallery_store.put("current_gallery", galleryinfo=galleryinfo)
        print self.get_root_window()
        App.get_running_app().root.next_screen("gallery_screen")

    def populate_front(self, *largs):
        # filter store
        filterstore = JsonStore(join(data_dir, "filterstore.json"))
        filters = filterstore.get("filters")
        filtertemp = filters["filters"]
        print filtertemp
        # ehentai link
        self.gidlist = []
        headers = {'User-agent': 'Mozilla/5.0'}
        r = requests.get("http://g.e-hentai.org/?page="+str(self.searchpage) +
                         "f_doujinshi="+str(filtertemp["doujinshi"]) +
                         "&f_manga="+str(filtertemp["manga"]) +
                         "&f_artistcg="+str(filtertemp["artistcg"]) +
                         "&f_gamecg="+str(filtertemp["gamecg"]) +
                         "&f_western="+str(filtertemp["western"]) +
                         "&f_non-h="+str(filtertemp["nonh"]) +
                         "&f_imageset="+str(filtertemp["imageset"]) +
                         "&f_cosplay="+str(filtertemp["cosplay"]) +
                         "&f_asianporn="+str(filtertemp["asianporn"]) +
                         "&f_misc="+str(filtertemp["misc"]) +
                         "&f_search="+self.searchword+"&f_apply=Apply+Filter",
                         headers=headers)
        self.searchpage += 1
        # pure html of ehentai link
        data = r.text

        soup = BS(data, fromEncoding='utf8')
        gallerylinks = []

        # grabs all the divs with class it5 which denotes the gallery on the
        # page
        for link in soup.findAll('div', {'class': 'it5'}):
            # grabs all the links, should only be gallery links as of 29th of
            # august 2015
            gallerylinks.append(link.find('a')["href"])

        for link in gallerylinks:
            splitlink = link.split('/')
            # grab the gallery token
            gtoken = splitlink[-2]
            # grab the gallery id
            gid = splitlink[-3]
            self.gidlist.append([gid, gtoken])
            print(self.gidlist)

        headers = {"Content-type": "application/json", "Accept": "text/plain",
                   'User-agent': 'Mozilla/5.0'}
        payload = {
            "method": "gdata",
            "gidlist": self.gidlist
            }

        self.grabthumbs(headers, payload)

    def grabthumbs(self, headers, payload, *largs):
        r = requests.post("http://g.e-hentai.org/api.php",
                          data=json.dumps(payload), headers=headers)
        requestdump = r.text
        requestdump.rstrip(os.linesep)
        requestjson = json.loads(requestdump)
        i = 0
        for gallery in requestjson["gmetadata"]:
            self.add_button(gallery)
            i += 1

    def add_button(self, gallery, *largs):
        gallerybutton = ThumbButton(
            source=gallery["thumb"],
            gallery_id=str(gallery["gid"]),
            gallery_token=str(gallery["token"]),
            pagecount=int(gallery["filecount"]),
            gallery_name=gallery["title"], allow_stretch=True)
        gallerybutton.bind(on_press=self.enter_gallery)
        buttoncontainer = BoxLayout(orientation="horizontal")
        buttoncontainer.add_widget(gallerybutton)
        buttoncontainer.add_widget(ScrollableTitle(titletext=gallery["title"]))
        self.ids.main_layout.add_widget(buttoncontainer)


class ScrollableTitle(ScrollView):

    titletext = StringProperty("")


class GalleryScreen(Screen):

    gallery_id = StringProperty("")
    gallery_token = StringProperty("")
    pagelinks = ListProperty([])
    pagecount = NumericProperty(0)
    gallery_name = StringProperty("")

    global data_dir

    def on_enter(self):
        self.ids.gallery_carousel.clear_widgets()
        gallery_store = JsonStore(join(data_dir, 'gallerystore.json'))
        if gallery_store.exists("current_gallery"):
            galleryinfo = gallery_store.get("current_gallery")
            self.gallery_id = galleryinfo["galleryinfo"][0]
            self.gallery_token = galleryinfo["galleryinfo"][1]
            self.pagecount = galleryinfo["galleryinfo"][2]
            self.gallery_name = galleryinfo["galleryinfo"][3]
        self.populate_gallery()

    def on_leave(self):
        self.ids.gallery_carousel.clear_widgets()
        print self.ids.gallery_carousel.slides
        self.gallery_id = ""
        self.gallery_token = ""
        self.pagelinks = []
        self.pagecount = 0
        self.gallery_name = ""

    def populate_gallery(self):
        # change placehold.it with
        gallerypages = float(self.pagecount) / float(40)
        pageregex = re.compile('http://g.e-hentai.org/s/\S{10}/\d{6}-\d+')

        if gallerypages.is_integer():
            print(gallerypages)
        else:
            gallerypages += 1

        headers = {'User-agent': 'Mozilla/5.0'}
        for i in range(int(gallerypages)):
            galleryrequest = requests.get("http://g.e-hentai.org/g/{}/{}/?p={}\
                                          ".format(self.gallery_id,
                                          self.gallery_token, i),
                                          headers=headers)

            soup = BS(galleryrequest.text)

            for a in soup.findAll(name="a", attrs={"href": pageregex}):
                self.pagelinks.append(a["href"])

        pagetimer = 0
        for page in self.pagelinks:
            # Clock.schedule_once(partial(self.grab_image, page), 2*pagetimer)
            self.grab_image(page)
            pagetimer += 1

    def grab_image(self, i, *largs):
        headers = {'User-agent': 'Mozilla/5.0'}
        pagerequest = requests.get(url=i, headers=headers)

        soup = BS(pagerequest.text)

        srctag = soup.findAll(name="img", attrs={"id": "img"})
        for each in srctag:
            src = each["src"]
        image = GalleryImage(source=src, allow_stretch=True)
        self.ids.gallery_carousel.add_widget(image)


class GalleryImage(Image):
    pass


class SearchPopup(Popup):

    global data_dir

    def savesearch(self):
        print(self.ids.searchstring.text)
        search_store = JsonStore(join(data_dir, 'search_store.json'))
        searchquery = self.ids.searchstring.text
        search_store.put("searchstring", searchphrase=searchquery)
        self.dismiss()


class SadpandaRoot(BoxLayout):

    def __init__(self, **kwargs):
        super(SadpandaRoot, self).__init__(**kwargs)
        # list of previous screens
        self.screen_list = []

    def next_screen(self, neoscreen):

        self.screen_list.append(self.ids.sadpanda_screen_manager.current)

        self.ids.sadpanda_screen_manager.current = neoscreen

    def goto_front(self, instance):
        print self.ids.sadpanda_screen_manager.current
        self.ids.sadpanda_screen_manager.switch_to(FrontScreen())
        self.ids.sadpanda_screen_manager.add_widget(GalleryScreen(id="gallery_\
                                                    screen",
                                                    name="gallery_screen"))
        self.screen_list.append("gallery_screen")

    def search_popup(self):
        spopup = SearchPopup()
        print(spopup)
        spopup.bind(on_dismiss=self.goto_front)
        spopup.open()

    def onBackBtn(self):
        # check if there are screens we can go back to
        if self.screen_list:
            print self.screen_list
            currentscreen = self.screen_list.pop()
            self.ids.sadpanda_screen_manager.current = currentscreen
            # Prevents closing of app
            return True
        # no more screens to go back to, close app
        return False

    def show_filters(self):
        fpop = FilterPopup()
        fpop.bind(on_dismiss=self.set_filters)
        fpop.open()

    def set_filters(self, instance):
        filters = {
            "doujinshi": 0,
            "manga": 0,
            "artistcg": 0,
            "gamecg": 0,
            "western": 0,
            "nonh": 0,
            "imageset": 0,
            "cosplay": 0,
            "asianporn": 0,
            "misc": 0}
        if instance.ids.doujinshi.state == "down":
            filters["doujinshi"] = 1
        if instance.ids.manga.state == "down":
            filters["manga"] = 1
        if instance.ids.artistcg.state == "down":
            filters["artistcg"] = 1
        if instance.ids.gamecg.state == "down":
            filters["gamecg"] = 1
        if instance.ids.western.state == "down":
            filters["western"] = 1
        if instance.ids.nonh.state == "down":
            filters["nonh"] = 1
        if instance.ids.imageset.state == "down":
            filters["imageset"] = 1
        if instance.ids.cosplay.state == "down":
            filters["cosplay"] = 1
        if instance.ids.asianporn.state == "down":
            filters["asianporn"] = 1
        if instance.ids.misc.state == "down":
            filters["misc"] = 1

        filterstore = JsonStore(join(data_dir, "filterstore.json"))
        filterstore.put("filters", filters=filters)


class FilterPopup(Popup):
    doujinshi = NumericProperty(0)
    manga = NumericProperty(0)
    artistcg = NumericProperty(0)
    gamecg = NumericProperty(0)
    western = NumericProperty(0)
    nonh = NumericProperty(0)
    imageset = NumericProperty(0)
    cosplay = NumericProperty(0)
    asianporn = NumericProperty(0)
    misc = NumericProperty(0)

    global data_dir

    def __init__(self, **kwargs):
        super(FilterPopup, self).__init__(**kwargs)
        filterjson = JsonStore(join(data_dir, "filterstore.json"))
        if filterjson.exists("filters"):
            self.doujinshi = filterjson["filters"]["filters"]["doujinshi"]
            self.manga = filterjson["filters"]["filters"]["manga"]
            self.artistcg = filterjson["filters"]["filters"]["artistcg"]
            self.gamecg = filterjson["filters"]["filters"]["gamecg"]
            self.western = filterjson["filters"]["filters"]["western"]
            self.nonh = filterjson["filters"]["filters"]["nonh"]
            self.imageset = filterjson["filters"]["filters"]["imageset"]
            self.cosplay = filterjson["filters"]["filters"]["cosplay"]
            self.asianporn = filterjson["filters"]["filters"]["asianporn"]
            self.misc = filterjson["filters"]["filters"]["misc"]
        if self.doujinshi == 1:
            self.ids.doujinshi.state = "down"
        if self.manga == 1:
            self.ids.manga.state = "down"
        if self.artistcg == 1:
            self.ids.artistcg.state = "down"
        if self.gamecg == 1:
            self.ids.gamecg.state = "down"
        if self.western == 1:
            self.ids.western.state = "down"
        if self.nonh == 1:
            self.ids.nonh.state = "down"
        if self.imageset == 1:
            self.ids.imageset.state = "down"
        if self.cosplay == 1:
            self.ids.cosplay.state = "down"
        if self.asianporn == 1:
            self.ids.asianporn.state = "down"
        if self.misc == 1:
            self.ids.misc.state = "down"

    def changeState(self, state, id):
        print state, id


class SadpandaApp(App):

    def __init__(self, **kwargs):
        super(SadpandaApp, self).__init__(**kwargs)
        global data_dir
        data_dir = getattr(self, 'user_data_dir')
        Window.bind(on_keyboard=self.onBackBtn)
        filterstore = JsonStore(join(data_dir, "filterstore.json"))
        # Makes sure only non-h is the default.
        filters = {
            "doujinshi": 0,
            "manga": 0,
            "artistcg": 0,
            "gamecg": 0,
            "western": 0,
            "nonh": 1,
            "imageset": 0,
            "cosplay": 0,
            "asianporn": 0,
            "misc": 0
            }
        filterstore.put("filters", filters=filters)

    def onBackBtn(self, window, key, *args):
        # user presses back button
        if key == 27:
            return self.root.onBackBtn()

    def on_pause(self):
        return True

    def build(self):
        return SadpandaRoot()

if __name__ == "__main__":
    SadpandaApp().run()
