import json
import sys
import unittest
from typing import List
from pathlib import Path
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException



with open(Path(__file__).parent.absolute().as_posix() + '/config.json', encoding='utf-8') as json_file:
    json_data = json.load(json_file)

    url_under_test = json_data['tested_url']
    webdriver_url = json_data['webdriver_url']
    browsers = json_data['browsers']

def on_platforms(platforms):
    def decorator(base_class):
        module = sys.modules[base_class.__module__].__dict__
        for i, platform in enumerate(platforms):
            var = dict(base_class.__dict__)
            var['desired_capabilities'] = platform
            name = "%s_%s" % (base_class.__name__, i + 1)
            module[name] = type(name, (base_class,), var)
    return decorator

class CustomError(Exception):
    pass

@on_platforms(browsers)
class PythonTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print(cls.__name__)
        cls.desired_capabilities['name'] = cls.__name__
        cls.driver = webdriver.Remote(
            desired_capabilities=cls.desired_capabilities,
            command_executor=webdriver_url)
        cls.driver.implicitly_wait(30)

    def keys_exists(self, element: dict, *keys: str) -> bool:
        """ Check if *keys exists in a nested dict
        :param element: a nested dict
        :param *keys: multiple strings containing the expected keys

        :return: True if the given keys were found otherwise False
        """

        if not isinstance(element, dict):
            raise AttributeError('keys_exists() expects dict as first argument.')
        if len(keys) == 0:
            raise AttributeError('keys_exists() expects at least two arguments, one given.')

        _element = element
        for key in keys:
            try:
                _element = _element[key]
            except KeyError:
                return False
        return True

    def get_numbers_from_string(self, input_str: str) -> List[int]:
        """ Retrieves the numbers from a string
        :param input_str: input string that contains some numbers inside

        :return: a list of integers from the input string
        """

        if "," in input_str:
            input_str = input_str.replace(",", "")
        no_list = [int(item) for item in input_str.split() if item.isdigit()]
        return no_list

    def check_apartments_dubai(self, input_str: str, action: str, type: str, location: str) -> bool:
        """ Retrieves the to rent dubai apartments urls
        :param input_str: input string that represents an url
        :param type: expected value for the action (eq.: to-rent, for-sale)
        :param type: expected value to be searched as property type
        :param location: expected value to be searched as location of the property

        :return: True if to-rent/apartments/dubai present in input_str, False otherwise
        """
        url_list = input_str.split('/')
        if action in url_list:
            index = url_list.index(action)
            if url_list[index + 1] == type and url_list[index + 2] == location:
                return True
        return False

    def check_valid_url(self, url: str) -> bool:
        """
        Checks if an url is valid
        :param url: string that represents the url

        :return: True if url is valid, False otherwise
        """
        req = requests.get(url)
        print(req)
        valid_flag = True
        if req.status_code != requests.codes['ok']:
            valid_flag = False
        return valid_flag

    def test_results_match_search_criteria(self):
        """
        Verify that all displayed properties contain the selected location
        """
        driver = self.driver
        driver.get(url_under_test)
        self.assertEqual(driver.title, json_data['title'], "Wrong title!")

        # Select Buy from drop down list
        driver.find_element_by_xpath(json_data['dd_btn_xpath']).click()
        driver.find_element_by_xpath(json_data['buy_btn_xpath']).click()

        # Input the location to Dubai Marina
        location_elem = \
            WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, json_data['location_xpath'])))

        # location_elem = driver.find_element_by_xpath(json_data['location_xpath'])
        location_elem.send_keys(json_data['location'])

        # check that Dubai Marina is the first item in the autocomplete list
        try:
            WebDriverWait(driver, 30).until(EC.text_to_be_present_in_element
                                            ((By.XPATH, json_data["autocomplete_first_elem"]), json_data['location']))
            location_elem.send_keys(Keys.ENTER)
        except TimeoutException:
            print("Autocomplete list is not updated in due time!")
            sys.exit(1)

        # Click on FIND button
        driver.find_element_by_link_text(json_data['find_btn']).click()

        # Handle the banner if it appears
        pop_up = driver.find_elements_by_xpath(json_data['banner'])
        if pop_up:
            pop_up[0].click()

        # Entries / page
        entries_page = driver.find_element_by_xpath(json_data['page_summary']).text
        no_list = self.get_numbers_from_string(entries_page)

        valid_entry_counter = 0
        page_no = 1

        while True:
            try:
                # Explicit wait for the DEAL OF THE WEEK span
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, json_data['deal'])))

                # Find all items that uses the application/ld+json script
                parent_elem = WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, json_data['script_class'])))

                items = parent_elem.find_elements_by_xpath(json_data['script_type'])

                for item in items:
                    item_str = item.get_attribute("innerHTML")
                    item_dict = json.loads(item_str)

                    # Check only the entries that have an address as a key
                    if self.keys_exists(item_dict, "address", "addressLocality"):
                        valid_entry_counter += 1
                        self.assertEqual(item_dict["address"]["addressLocality"].lower(), json_data["location"].lower(),
                                         "Wrong location found: {}!".format(item_dict["address"]["addressLocality"]))

                # Navigating to the next page
                WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, json_data['next_page']))).click()

                # Check that the counted valid entries are as expected (eq.: 24 items/page + deal of the week)
                self.assertEqual(valid_entry_counter, (no_list[1] + 1) * page_no,
                                 "More entries encountered on page {}".format(page_no))
                page_no += 1

            except TimeoutException:
                # Last page was reached
                break

    def test_valid_links(self):
        """
        Verify that links under ' Dubai apartments' are functioning correctly
        """
        driver = self.driver

        driver.get(url_under_test)
        self.assertEqual(driver.title, json_data['title'], "Wrong title!")

        # Select To Rent button
        driver.find_element_by_xpath(json_data['to_rent_btn']).click()

        # Retrieve all links
        elements = driver.find_elements_by_xpath(json_data['all_links'])
        dubai_apartments_list = []
        for element in elements:
            url = element.get_attribute("href")
            if self.check_apartments_dubai(url, "to-rent", "apartments", "dubai"):
                # Check url validity
                validity = self.check_valid_url(url)
                self.assertTrue(validity, "URL:{} is not valid".format(url))
                dubai_apartments_list.append(url)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

if __name__ == "__main__":
    unittest.main()
