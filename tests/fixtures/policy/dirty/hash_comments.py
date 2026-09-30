LIMIT = 40


def clamp(value):
    # a hash comment, only a finding when the policy forbids hash markers
    return min(value, LIMIT)
