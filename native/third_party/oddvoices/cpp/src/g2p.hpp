#pragma once

#include <map>
#include <vector>
#include <set>
#include <string>
#include <sstream>

namespace oddvoices {
namespace g2p {

extern std::set<unsigned char> k_punctuation;
extern std::vector<std::string> k_allPhonemes;
extern std::vector<std::string> k_vowels;
extern std::map<std::string, std::string> k_vvFixers;
extern std::map<std::string, std::vector<std::string>> k_phonemeAliases;
extern std::map<std::string, std::string> k_arpabetToXSAMPA;
extern std::map<std::string, std::vector<std::string>> k_guessPronunciations;
extern std::map<std::string, std::vector<std::string>> k_cmudictExceptions;

std::vector<std::string> parsePronunciation(std::string);
std::vector<std::string> fixVVDiphones(const std::vector<std::string>& pronunciation);

/// G2P stands for Grapheme to Phoneme, the portion of the singing synthesizer
/// system that decides the pronunciations of words.
///
/// Creating and using a G2P is not real-time safe, and should never be done
/// on the audio thread.
class G2P
{
public:
    G2P(std::string cmudictFile);

    std::vector<std::string> pronounce(std::string);
    std::vector<std::string> pronounceWord(std::string);

private:
    void loadCmudict(std::string fileName);

    std::map<std::string, std::vector<std::string>> m_pronunciationDict;
};

} // namespace g2p
} // namespace oddvoices
