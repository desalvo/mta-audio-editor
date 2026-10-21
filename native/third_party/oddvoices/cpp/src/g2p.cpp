// MTA modification, 2026-10-20 (0.3.0-r210): UTF-8 filesystem paths for Windows.
#include <filesystem>
#include <algorithm>
#include <fstream>
#include <optional>
#include <string_view>

#include "g2p.hpp"

namespace oddvoices {
namespace g2p {

constexpr auto k_leftBrace = "{";
constexpr auto k_rightBrace = "}";

std::set<unsigned char> k_punctuation = {
    '.', '!', ',', ':', '"', '\'', '(', ')', '[', ']', '-'
};

std::vector<std::string> k_allPhonemes = {
    "l",
    "r",
    "j",
    "w",
    "m",
    "n",
    "N",
    "h",
    "k",
    "g",
    "p",
    "b",
    "t",
    "d",
    "tS",
    "dZ",
    "f",
    "v",
    "T",
    "D",
    "s",
    "z",
    "S",
    "Z",
    "{}",
    "@`",
    "A",
    "I",
    "E",
    "@",
    "u",
    "U",
    "i",
    "oU",
    "eI",
    "aI",
    "OI",
    "aU",
    "_"
};

std::vector<std::string> k_vowels = {
    "{}",
    "@`",
    "A",
    "I",
    "E",
    "@",
    "u",
    "U",
    "i",
    "oU",
    "eI",
    "aI",
    "OI",
    "aU"
};

std::map<std::string, std::string> k_vvFixers = {
    {"i", "j"},
    {"aI", "j"},
    {"eI", "j"},
    {"OI", "j"},
    {"u", "w"},
    {"aU", "w"},
    {"oU", "w"},
    {"@`", "r"}
};

std::map<std::string, std::vector<std::string>> k_phonemeAliases = {
    {"V", {"@"}},
    {"3`", {"@`"}},
    {"O", {"A"}},
    {"&", {"{}"}},
    {k_leftBrace, {"{}"}},
    {"Or", {"oU", "r"}},
    {"?", {"_"}},
    {" ", {"_"}}
};

std::map<std::string, std::string> k_arpabetToXSAMPA = {
    {"AA", "A"},
    {"AE", "{}"},
    {"AH", "@"},
    {"AO", "O"},
    {"AW", "aU"},
    {"AY", "aI"},
    {"B", "b"},
    {"CH", "tS"},
    {"D", "d"},
    {"DH", "D"},
    {"EH", "E"},
    {"ER", "@`"},
    {"EY", "eI"},
    {"F", "f"},
    {"G", "g"},
    {"HH", "h"},
    {"IH", "I"},
    {"IY", "i"},
    {"JH", "dZ"},
    {"K", "k"},
    {"L", "l"},
    {"M", "m"},
    {"N", "n"},
    {"NG", "N"},
    {"OW", "oU"},
    {"OY", "OI"},
    {"P", "p"},
    {"R", "r"},
    {"S", "s"},
    {"SH", "S"},
    {"T", "t"},
    {"TH", "T"},
    {"UH", "U"},
    {"UW", "u"},
    {"V", "v"},
    {"W", "w"},
    {"Y", "j"},
    {"Z", "z"},
    {"ZH", "Z"}
};

std::map<std::string, std::vector<std::string>> k_guessPronunciations = {
    {"a", {"{}"}},
    {"ai", {"aI"}},
    {"ar", {"A", "r"}},
    {"au", {"aU"}},
    {"augh", {"A"}},
    {"b", {"b"}},
    {"c", {"k"}},
    {"ch", {"tS"}},
    {"d", {"d"}},
    {"e", {"E"}},
    {"ei", {"eI"}},
    {"ee", {"i"}},
    {"ea", {"i"}},
    {"er", {"@`"}},
    {"f", {"f"}},
    {"g", {"g"}},
    {"h", {"h"}},
    {"i", {"I"}},
    {"ie", {"aI"}},
    {"igh", {"aI"}},
    {"j", {"dZ"}},
    {"k", {"k"}},
    {"l", {"l"}},
    {"m", {"m"}},
    {"n", {"n"}},
    {"ng", {"N"}},
    {"o", {"oU"}},
    {"oi", {"OI"}},
    {"oo", {"u"}},
    {"ou", {"aU"}},
    {"ough", {"A"}},
    {"ow", {"aU"}},
    {"p", {"p"}},
    {"q", {"k", "w"}},
    {"r", {"r"}},
    {"s", {"s"}},
    {"sh", {"S"}},
    {"t", {"t"}},
    {"th", {"T"}},
    {"u", {"@"}},
    {"ur", {"@`"}},
    {"v", {"v"}},
    {"w", {"w"}},
    {"x", {"k", "s"}},
    {"y", {"j"}},
    {"y$", {"i"}},
    {"z", {"z"}}
};

std::map<std::string, std::vector<std::string>> k_cmudictExceptions = {
    {"and", {"{}", "n", "d"}},
    {"every", {"E", "v", "r", "i"}},
    {"oddvoices", {"A", "d", "v", "OI", "s", "E", "z"}},
    {"chesnokov", {"tS", "E", "z", "n", "oU", "k", "A", "v"}}
};

static bool isVowel(std::string phoneme)
{
    for (auto const& candidate : k_vowels) {
        if (candidate == phoneme) {
            return true;
        }
    }
    return false;
}

G2P::G2P(std::string cmudictFile)
{
    loadCmudict(cmudictFile);
}

static std::vector<std::string> splitWords(std::string string)
{
    std::vector<std::string> result;
    std::istringstream stringStream(string);
    std::string word;
    while (std::getline(stringStream, word, ' ')) {
        if (!word.empty()) {
            result.push_back(word);
        }
    }
    return result;
}

static void toLower(std::string& string)
{
    std::transform(
        string.begin(),
        string.end(),
        string.begin(),
        [](unsigned char c) { return std::tolower(c); }
    );
}

static std::string arpabetToXSAMPA(const std::string& string)
{
    auto lastCharacter = string[string.size() - 1];
    if ('0' <= lastCharacter && lastCharacter <= '9') {
        return k_arpabetToXSAMPA[string.substr(0, string.size() - 1)];
    }
    return k_arpabetToXSAMPA[string];
}

static std::vector<std::string> tokenize(std::string text)
{
    auto islands = splitWords(text);
    std::vector<std::string> words;
    for (auto& island : islands) {
        if (island.front() == '/' && island.back() == '/') {
            words.push_back(island);
        } else {
            std::string newWord = "";
            auto lowerIsland = island;
            toLower(lowerIsland);
            for (auto& c : lowerIsland) {
                if (!('a' <= c && c <= 'z') && c != '\'') {
                    if (!newWord.empty()) {
                        words.push_back(newWord);
                        newWord = "";
                    }
                } else {
                    newWord.push_back(c);
                }
            }
            if (!newWord.empty()) {
                words.push_back(newWord);
            }
        }
    }
    return words;
}

/// OOV stands for "out of vocabulary." This function tries to guess the pronunciation
/// of the input word using manually written heuristics.
static std::vector<std::string> pronounceOOV(std::string word)
{
    // Create a sorted list of keys from k_guessPronunciations in descending order of
    // length, so longer keys get matched first.
    std::vector<std::string> keys;
    for (auto const& [key, value] : k_guessPronunciations) {
        keys.push_back(key);
    }
    std::sort(keys.begin(), keys.end(), [](const std::string& a, const std::string& b) {
        return a.size() > b.size();
    });
    std::string remainingWord = word + "$";
    std::vector<std::string> resultPass1;
    while (remainingWord.size() != 0) {
        bool keyFound = false;
        for (auto const& key : keys) {
            if (
                remainingWord.size() >= key.size()
                && remainingWord.substr(0, key.size()) == key
            ) {
                remainingWord = remainingWord.substr(
                    key.size(), remainingWord.size() - key.size()
                );
                auto& newPhonemes = k_guessPronunciations[key];
                resultPass1.insert(
                    resultPass1.end(),
                    newPhonemes.begin(),
                    newPhonemes.end()
                );
                keyFound = true;
                break;
            }
        }
        if (!keyFound) {
            remainingWord = remainingWord.substr(1, remainingWord.size() - 1);
        }
    }
    std::vector<std::string> resultPass2;
    std::optional<std::string> lastPhoneme;
    for (auto const& phoneme : resultPass1) {
        if (phoneme != lastPhoneme) {
            resultPass2.push_back(phoneme);
        }
        lastPhoneme = phoneme;
    }
    return resultPass2;
}

/// Change /Or/ to /oUr/ and /O/ to /A/.
static void performCotCaughtMerger(std::vector<std::string>& pronunciation)
{
    int numPhonemes = static_cast<int>(pronunciation.size());
    for (int i = 0; i < numPhonemes; i++) {
        if (pronunciation[i] == "O") {
            if (i + 1 < numPhonemes && pronunciation[i + 1] == "r") {
                pronunciation[i] = "oU";
            } else {
                pronunciation[i] = "A";
            }
        }
    }
}

std::vector<std::string> fixVVDiphones(const std::vector<std::string>& pronunciation)
{
    std::vector<std::string> result;
    std::string lastPhoneme = "";
    for (auto const& phoneme : pronunciation) {
        if (isVowel(phoneme) && k_vvFixers.count(lastPhoneme) > 0) {
            result.push_back(k_vvFixers[lastPhoneme]);
        }
        result.push_back(phoneme);
        lastPhoneme = phoneme;
    }
    return result;
}

static std::vector<std::string> normalizePronunciation(std::vector<std::string> pronunciation)
{
    std::vector<std::string> result;
    if (pronunciation.empty()) {
        return { "_" };
    }
    if (pronunciation.front() != "_") {
        result.push_back("_");
    }
    result.insert(result.end(), pronunciation.begin(), pronunciation.end());
    if (pronunciation.back() != "_") {
        result.push_back("_");
    }
    return result;
}

std::vector<std::string> parsePronunciation(std::string pronunciation)
{
    std::vector<std::string> result;
    auto remainingPronunciation = std::string_view(pronunciation);

    auto allPhonemes = k_allPhonemes;
    for (auto const& [key, value] : k_phonemeAliases) {
        allPhonemes.push_back(key);
    }

    std::sort(
        allPhonemes.begin(),
        allPhonemes.end(),
        [](const std::string& a, const std::string& b) {
            return a.size() > b.size();
        }
    );

    while (remainingPronunciation.size() != 0) {
        bool phonemeFound = false;
        for (auto const& phoneme : allPhonemes) {
            if (
                remainingPronunciation.size() >= phoneme.size()
                && remainingPronunciation.substr(0, phoneme.size()) == phoneme
            ) {
                if (k_phonemeAliases.count(phoneme) > 0) {
                    auto& newPhonemes = k_phonemeAliases[phoneme];
                    result.insert(result.end(), newPhonemes.begin(), newPhonemes.end());
                } else {
                    result.push_back(phoneme);
                }
                remainingPronunciation.remove_prefix(phoneme.size());
                phonemeFound = true;
                break;
            }
        }
        if (!phonemeFound) {
            remainingPronunciation.remove_prefix(1);
        }
    }

    return result;
}

std::vector<std::string> G2P::pronounceWord(std::string word)
{
    std::vector<std::string> result;
    if (word[0] == '/') {
        result = parsePronunciation(word.substr(1, word.size() - 2));
    } else if (m_pronunciationDict.count(word) == 1) {
        result = m_pronunciationDict[word];
        performCotCaughtMerger(result);
    } else {
        result = pronounceOOV(word);
    }
    result = fixVVDiphones(result);
    result = normalizePronunciation(result);
    return result;
}

void G2P::loadCmudict(std::string fileName)
{
    std::ifstream stream(std::filesystem::u8path(fileName));
    std::string line;
    while (std::getline(stream, line)) {
        if (line.size() >= 3 && line.substr(0, 3) == ";;;") {
            continue;
        }
        auto words = splitWords(line);

        auto word = words[0];
        toLower(word);

        std::vector<std::string> pronunciation;
        for (int i = 1; i < static_cast<int>(words.size()); i++) {
            pronunciation.push_back(arpabetToXSAMPA(words[i]));
        }
        m_pronunciationDict[word] = pronunciation;
    }
    for (auto const& [word, pronunciation] : k_cmudictExceptions) {
        m_pronunciationDict[word] = pronunciation;
    }
}


std::vector<std::string> G2P::pronounce(std::string text)
{
    auto words = tokenize(text);
    std::vector<std::string> result;
    for (auto& word : words) {
        auto pronunciation = pronounceWord(word);
        result.insert(result.end(), pronunciation.begin(), pronunciation.end());
    }
    return result;
}

} // namespace g2p
} // namespace oddvoices
