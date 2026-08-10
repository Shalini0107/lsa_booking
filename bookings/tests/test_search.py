from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from bookings.models import LSAProfile, Skill


class LSASearchTests(TestCase):
    """Covers T-04 and the N+1 optimization requirement (SRS Sections 12, 15)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('lsa-search')

        self.autism = Skill.objects.create(name='Autism Support')
        self.dyslexia = Skill.objects.create(name='Dyslexia')

        self.available_lsa = LSAProfile.objects.create(name='Alex Smith', is_available=True)
        self.available_lsa.skills.set([self.autism, self.dyslexia])

        self.unavailable_lsa = LSAProfile.objects.create(name='Sam Lee', is_available=False)
        self.unavailable_lsa.skills.set([self.autism])

        self.other_skill_lsa = LSAProfile.objects.create(name='Priya Patel', is_available=True)
        self.other_skill_lsa.skills.set([self.dyslexia])

    def test_search_filters_by_skill_and_excludes_unavailable(self):
        # T-04
        response = self.client.get(self.url, {'skills': 'Autism Support'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [lsa['name'] for lsa in response.data]
        self.assertEqual(names, ['Alex Smith'])

    def test_search_without_filter_returns_all_available(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {lsa['name'] for lsa in response.data}
        self.assertEqual(names, {'Alex Smith', 'Priya Patel'})

    def test_search_by_nonexistent_skill_returns_empty(self):
        response = self.client.get(self.url, {'skills': 'Nonexistent Skill'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_search_is_n_plus_one_safe(self):
        # Adding more matching LSAs must not increase the query count -
        # this is what demonstrates prefetch_related is doing its job
        # instead of querying skills once per LSA in a loop.
        for i in range(5):
            lsa = LSAProfile.objects.create(name=f'Extra LSA {i}', is_available=True)
            lsa.skills.set([self.autism])

        with self.assertNumQueries(2):  # 1 for LSAProfile rows, 1 prefetch for skills
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)  # 2 original available + 5 extra
